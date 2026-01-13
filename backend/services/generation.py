import os
import json
import time
import asyncio
import base64
import shutil
import urllib.parse
from typing import AsyncGenerator, Dict
from backend.core.paths import OUTPUTS_DIR, ASSETS_DIR
from backend.core.config import load_config
from backend.core.utils import sanitize_filename, clean_string, create_sse_event, get_time
from backend.services.comfyui_service import check_comfyui_connection, fetch_available_models, fetch_available_ipadapters, load_workflow_template, prepare_workflow
from backend.comfyui_client import ComfyUIClient
from backend.services.openai_service import get_openai_client
from backend.core.schemas import ReferenceImageRequest, UploadRequest

# Global state
generation_state = {
    "status": "idle" # running, stopped, finish_early
}

def get_generation_status():
    return generation_state["status"]

def set_generation_status(status: str):
    if status in ["idle", "running", "stopped", "finish_early"]:
        generation_state["status"] = status
        return True
    return False

async def upload_reference(req: UploadRequest):
    try:
        if not req.image or not req.filename:
            return {"success": False, "error": "Missing image or filename"}

        image_data = req.image
        if "," in image_data:
            image_data = image_data.split(",")[1]
            
        decoded = base64.b64decode(image_data)
        timestamp = int(time.time() * 1000)
        filename = f"uploaded_ref_{timestamp}_{sanitize_filename(req.filename)}"
        file_path = os.path.join(ASSETS_DIR, filename)
        
        os.makedirs(ASSETS_DIR, exist_ok=True)
        
        with open(file_path, "wb") as f:
            f.write(decoded)
            
        return {"success": True, "path": f"http://localhost:3501/assets/{filename}", "serverPath": file_path}
    except Exception as e:
        print(f"Upload Error: {e}")
        return {"success": False, "error": str(e)}

async def generate_reference_image(req: ReferenceImageRequest):
    config = load_config()
    protagonist_prompt = config.get("prompts", {}).get("protagonist_prompt", "A majestic wild animal")
    
    if req.style == "animation":
        base_prompt = config.get("prompts", {}).get("style_animation", "")
        negative_prompt = config.get("prompts", {}).get("negative_prompt_animation", "")
        cut_desc = req.cut.get("description", "")
        subject_desc = f"{protagonist_prompt}, {cut_desc}"
        positive_prompt = base_prompt.replace("{{subject_description}}", subject_desc)
    else:
        negative_prompt = config.get("prompts", {}).get("negative_prompt_photoreal", "")
        if not negative_prompt:
             negative_prompt = config.get("prompts", {}).get("negative_prompt", "")
        cut_description = req.cut.get("description", "")
        positive_prompt = f"photorealistic, 8K UHD, {protagonist_prompt}, {cut_description}"
    
    comfyui_server = "127.0.0.1:8188"
    if not check_comfyui_connection(host=comfyui_server.split(':')[0], port=int(comfyui_server.split(':')[1])):
         return {"success": False, "error": "❌ ComfyUI 서버 연동 실패"}

    try:
        workflow_template = load_workflow_template("reference_generation")
        if not workflow_template:
            raise Exception("Workflow template not found")
        
        import random
        seed = random.randint(0, 2**32 - 1)
        selected_model = config.get("selected_model", "RealVisXL_V5.0.safetensors")
        
        available_models = await fetch_available_models(config)
        if available_models:
            if selected_model not in available_models:
                selected_model = available_models[0]

        is_long = req.mode.lower() == "long" or "long form" in req.mode.lower()
        width = 1920 if is_long else 1080
        height = 1080 if is_long else 1920

        workflow = prepare_workflow(workflow_template, {
            "positive_prompt": positive_prompt,
            "negative_prompt": negative_prompt,
            "seed": seed,
            "cut_number": req.cut.get("cutNumber", 1),
            "ckpt_name": selected_model,
            "width": width,
            "height": height
        })

        client = ComfyUIClient(comfyui_server)
        result = client.queue_prompt(workflow)
        prompt_id = result.get("prompt_id")
        
        if not prompt_id: raise Exception("Failed to queue prompt")
        
        max_wait = 120
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            history = client.get_history(prompt_id)
            if prompt_id in history:
                outputs = history[prompt_id].get("outputs", {})
                for node_id, node_output in outputs.items():
                    if "images" in node_output:
                        image_info = node_output["images"][0]
                        image_data = client.get_image(image_info["filename"], image_info.get("subfolder", ""), image_info.get("type", "output"))
                        image_base64 = base64.b64encode(image_data).decode('utf-8')
                        image_url = f"data:image/png;base64,{image_base64}"
                        reference_path = os.path.join(OUTPUTS_DIR, f"reference_{prompt_id}.png")
                        with open(reference_path, 'wb') as f:
                            f.write(image_data)
                        return {
                            "success": True, "imageUrl": image_url, "imagePath": reference_path,
                            "protagonistPrompt": protagonist_prompt, "cutNumber": req.cut.get("cutNumber", 1),
                            "source": "comfyui", "seed": seed
                        }
                break
            await asyncio.sleep(1)
        
        raise Exception("ComfyUI timeout")
    except Exception as e:
        return {"success": False, "error": str(e)}

async def real_comfyui_process_generator(params: dict, topic: str, reference_image: str = "", skip_generation: bool = False) -> AsyncGenerator[dict, None]:
    if not skip_generation and not check_comfyui_connection():
        yield create_sse_event({"type": "error", "message": "❌ ComfyUI 서버(127.0.0.1:8188)가 켜져있지 않습니다. 실행 후 다시 시도해주세요."})
        return
    
    config = load_config()
    comfyui_server = "127.0.0.1:8188"
    client = ComfyUIClient(comfyui_server)
    
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    folder_name = f"{timestamp}_{sanitize_filename(params['selected_title'] or topic)}"
    project_dir = os.path.join(OUTPUTS_DIR, folder_name)
    os.makedirs(project_dir, exist_ok=True)
    
    total_cuts = params['total_cuts']
    generation_state["status"] = "running"
    
    yield create_sse_event({"type": "log", "message": f"🚀 프로젝트 생성: {folder_name}"})
    yield create_sse_event({"type": "log", "message": f"📸 총 {total_cuts}컷 이미지 생성 시작 (Real ComfyUI)"})

    workflow_template = load_workflow_template("base_generation")
    if not workflow_template:
        yield create_sse_event({"type": "error", "message": "❌ 기본 워크플로우(base_generation.json)를 찾을 수 없습니다."})
        return

    # Model Selection
    selected_model = config.get("selected_model", "RealVisXL_V5.0.safetensors")
    available_models = await fetch_available_models(config)
    if available_models and selected_model not in available_models:
        fallback_model = available_models[0]
        yield create_sse_event({"type": "log", "message": f"⚠️ 모델 '{selected_model}'을(를) 찾을 수 없어 '{fallback_model}'을(를) 사용합니다."})
        selected_model = fallback_model

    # IPAdapter Selection
    selected_ipadapter = "ip-adapter-plus_sdxl_vit-h.safetensors" # Default
    available_ipadapters = await fetch_available_ipadapters(config)
    if available_ipadapters:
        # 1. Exact match
        if selected_ipadapter in available_ipadapters:
            pass # Keep default
        else:
            # 2. Search for best match (sdxl + plus)
            best_match = next((m for m in available_ipadapters if "sdxl" in m.lower() and "plus" in m.lower()), None)
            # 3. Search for any sdxl
            if not best_match:
                best_match = next((m for m in available_ipadapters if "sdxl" in m.lower()), None)
            
            if best_match:
                 yield create_sse_event({"type": "log", "message": f"⚠️ IPAdapter 모델 '{selected_ipadapter}'이(가) 없어 '{best_match}'(으)로 대체합니다."})
                 selected_ipadapter = best_match
            else:
                 yield create_sse_event({"type": "log", "message": f"⚠️ 호환되는 순정 SDXL IPAdapter 모델을 찾지 못했습니다. (생성 실패 가능성 있음)"})

    # Reference Image Processing
    if reference_image and reference_image.startswith("http"):
        if "/assets/" in reference_image:
             filename = reference_image.split("/assets/")[-1]
             possible_path = os.path.join(ASSETS_DIR, filename)
             if os.path.exists(possible_path):
                 reference_image = possible_path
                 yield create_sse_event({"type": "log", "message": f"🔗 URL 참조 이미지 로컬 변환: {filename}"})
    elif reference_image and reference_image.startswith("data:image"):
        try:
            header, encoded = reference_image.split(",", 1)
            data = base64.b64decode(encoded)
            ext = "jpg" if "jpeg" in header else "png"
            timestamp = int(time.time() * 1000)
            filename = f"ref_base64_{timestamp}.{ext}"
            file_path = os.path.join(ASSETS_DIR, filename)
            os.makedirs(ASSETS_DIR, exist_ok=True)
            with open(file_path, "wb") as f:
                f.write(data)
            reference_image = file_path
            yield create_sse_event({"type": "log", "message": f"🖼️ Base64 참조 이미지 저장 완료: {filename}"})
        except Exception as e:
            yield create_sse_event({"type": "log", "message": f"⚠️ Base64 이미지 변환 실패: {e}"})

    current_reference_image = reference_image
    use_reference_chaining = config.get("use_reference_chaining", False)
    
    comfyui_input_dir = None
    possible_input_dirs = [
        os.path.join(config.get("comfyui_path", ""), "ComfyUI", "input"),
        os.path.join(config.get("comfyui_path", ""), "input"),
        os.path.join(os.path.dirname(config.get("comfyui_path", "")), "ComfyUI", "input")
    ]
    for d in possible_input_dirs:
        if os.path.exists(d) and os.path.isdir(d):
            comfyui_input_dir = d
            break
            
    # [FIX] Ensure reference image is in ComfyUI input directory
    if reference_image and comfyui_input_dir and os.path.exists(reference_image):
        try:
            ref_filename = os.path.basename(reference_image)
            target_path = os.path.join(comfyui_input_dir, ref_filename)
            if not os.path.exists(target_path):
                shutil.copy(reference_image, target_path)
            # Use only filename for ComfyUI LoadImage node, not absolute path
            reference_image = ref_filename 
            yield create_sse_event({"type": "log", "message": f"📂 참조 이미지를 ComfyUI Input 폴더로 복사: {ref_filename}"})
        except Exception as e:
             yield create_sse_event({"type": "log", "message": f"⚠️ 참조 이미지 복사 실패: {e}"})

    current_reference_image = reference_image

    generated_images = []
    cuts_data = params.get("cuts", [])
    
    if not cuts_data:
        yield create_sse_event({"type": "log", "message": "❌ 생성할 컷(Cut) 데이터가 없습니다."})
        yield create_sse_event({"type": "error", "message": "No cuts data found"})
        return

    for i, current_cut in enumerate(cuts_data):
        if generation_state["status"] == "stopped":
            yield create_sse_event({"type": "log", "message": "🛑 사용자 요청으로 생성이 중단되었습니다."})
            yield create_sse_event({"type": "error", "message": "Generation Stopped"})
            generation_state["status"] = "idle"
            return
        elif generation_state["status"] == "finish_early":
            yield create_sse_event({"type": "log", "message": "🏁 사용자 요청으로 조기 종료합니다."})
            generation_state["status"] = "idle"
            break
            
        cut_number = current_cut.get("cutNumber", i+1)
        yield create_sse_event({"type": "log", "message": f"⏳ [Cut {cut_number}/{total_cuts}] 생성 중...", "cutIndex": cut_number})
        
        active_workflow_template = None
        use_ref_setting = config.get("use_reference_image", True)
        
        if current_reference_image and use_ref_setting:
             try:
                 node_info = client.get_object_info("IPAdapterAdvanced")
                 if not node_info or "IPAdapterAdvanced" not in node_info:
                     yield create_sse_event({"type": "log", "message": "⚠️ 'IPAdapterAdvanced' 노드가 감지되지 않아 참조 이미지 기능을 건너뜁니다."})
                 else:
                     if i == 0:
                         yield create_sse_event({"type": "log", "message": f"🔄 [Cut {cut_number}] 초기 참조 이미지 사용: {os.path.basename(current_reference_image)}"})
                     else:
                         yield create_sse_event({"type": "log", "message": f"🔗 [Cut {cut_number}] 이전 컷을 참조하여 연속성 유지 중..."})
                     loaded_wf = load_workflow_template("reference_generation")
                     if loaded_wf: active_workflow_template = loaded_wf
             except Exception as e:
                 yield create_sse_event({"type": "log", "message": f"⚠️ 노드 확인 실패 (Safe Fallback): {e}"})

        if not active_workflow_template:
            if current_reference_image and not use_ref_setting:
                 yield create_sse_event({"type": "log", "message": "⚠️ 참조 이미지가 있지만 설정에서 비활성화되어 무시합니다."})
            active_workflow_template = load_workflow_template("base_generation")
        
        # Skip generation logic
        if skip_generation:
             # Just generate Veo prompt (sync for simplicity in skip mode or async is fine)
             veo_prompt_text = ""
             if current_cut:
                 try:
                    veo_system = config.get("prompts", {}).get("veo_video", "")
                    if veo_system:
                        veo_system = veo_system.replace("{{scene_description}}", current_cut.get("description", ""))
                        veo_system = veo_system.replace("{{physics_detail}}", current_cut.get("physicsDetail", "Dynamic movement"))
                        veo_system = veo_system.replace("{{sfx_guide}}", current_cut.get("sfxGuide", "Ambient sound"))
                        veo_system = veo_system.replace("{{emotion_level}}", str(current_cut.get("emotionLevel", 5)))
                        veo_system = veo_system.replace("{{character_tag}}", current_cut.get("characterTag", "Main Character"))
                        
                        openai_client = get_openai_client()
                        if openai_client:
                             veo_resp = await asyncio.to_thread(openai_client.chat.completions.create, model="gpt-5-mini-2025-08-07", messages=[{"role": "system", "content": veo_system}, {"role": "user", "content": "Generate 5-element Veo prompt."}])
                             veo_prompt_text = veo_resp.choices[0].message.content
                    current_cut["videoPrompt"] = veo_prompt_text
                    current_cut["veo_generated"] = True
                    # Prompt Construction (for Meta)
                    if params.get("style") == "animation":
                         anim_template = config.get("prompts", {}).get("style_animation", "")
                         desc = clean_string(current_cut.get("description", ""))
                         char_p = clean_string(params.get("character_prompt", "Character"))
                         subject_desc = f"{char_p}, {desc}"
                         positive_prompt = anim_template.replace("{{subject_description}}", subject_desc)
                    else:
                        desc = clean_string(current_cut.get("description", ""))
                        physics = clean_string(current_cut.get("physicsDetail", ""))
                        lighting = clean_string(current_cut.get("lightingCondition", ""))
                        weather = clean_string(current_cut.get("weatherAtmosphere", ""))
                        char_prompt = clean_string(params.get("character_prompt", "")) if current_cut.get("characterTag") else ""
                        positive_template = config.get("prompts", {}).get("positive_prompt_template", "photorealistic, 8K UHD, {{scene}}")
                        scene_text = f"{physics}, {lighting}, {weather}, {char_prompt}"
                        positive_prompt = positive_template.replace("{{scene}}", scene_text)
                    
                    if current_cut:
                        current_cut["imagePrompt"] = positive_prompt
                        
                 except Exception as e:
                    print(f"Skipped Veo Error: {e}")
             
             yield create_sse_event({"type": "log", "message": f"⏭️ [Cut {i}] 이미지 생성 건너뜀 (프롬프트만 생성 완료)"})
             continue

        try:
            # Prompt Construction
            if params.get("style") == "animation":
                anim_template = config.get("prompts", {}).get("style_animation", "")
                desc = clean_string(current_cut.get("description", ""))
                char_p = clean_string(params.get("character_prompt", "Character"))
                subject_desc = f"{char_p}, {desc}"
                positive_prompt = anim_template.replace("{{subject_description}}", subject_desc)
                raw_neg = config.get("prompts", {}).get("negative_prompt_animation", "")
                negative_prompt = clean_string(raw_neg)
            elif current_cut.get("imagePrompt"):
                positive_prompt = clean_string(current_cut.get('imagePrompt', ''))
                raw_neg = config.get("prompts", {}).get("negative_prompt", "bad quality, blurry")
                negative_prompt = clean_string(raw_neg)
            else:
                desc = clean_string(current_cut.get("description", ""))
                physics = clean_string(current_cut.get("physicsDetail", ""))
                lighting = clean_string(current_cut.get("lightingCondition", ""))
                weather = clean_string(current_cut.get("weatherAtmosphere", ""))
                char_prompt = clean_string(params.get("character_prompt", "")) if current_cut.get("characterTag") else ""
                positive_template = config.get("prompts", {}).get("positive_prompt_template", "photorealistic, 8K UHD, {{scene}}")
                scene_text = f"{physics}, {lighting}, {weather}, {char_prompt}"
                positive_prompt = positive_template.replace("{{scene}}", scene_text)
                raw_neg = config.get("prompts", {}).get("negative_prompt", "bad quality")
                negative_prompt = clean_string(raw_neg)

            if current_cut:
                current_cut["imagePrompt"] = positive_prompt

            # Veo Prompt Generation
            veo_task = None
            if current_cut:
                 try:
                    veo_system = config.get("prompts", {}).get("veo_video", "")
                    if veo_system:
                        veo_system = veo_system.replace("{{scene_description}}", current_cut.get("description", ""))
                        veo_system = veo_system.replace("{{physics_detail}}", current_cut.get("physicsDetail", "Dynamic movement"))
                        veo_system = veo_system.replace("{{sfx_guide}}", current_cut.get("sfxGuide", "Ambient sound"))
                        veo_system = veo_system.replace("{{emotion_level}}", str(current_cut.get("emotionLevel", 5)))
                        veo_system = veo_system.replace("{{character_tag}}", current_cut.get("characterTag", "Main Character"))
                        
                        openai_client = get_openai_client()
                        if openai_client:
                             # Schedule task, await later
                             veo_task = asyncio.create_task(asyncio.to_thread(openai_client.chat.completions.create, model="gpt-5-mini-2025-08-07", messages=[{"role": "system", "content": veo_system}, {"role": "user", "content": "Generate 5-element Veo prompt."}]))
                 except Exception as e:
                    print(f"Veo Prompt Setup Error: {e}")

            import random
            seed = random.randint(0, 2**32 - 1)
            workflow = prepare_workflow(active_workflow_template, {
                "positive_prompt": positive_prompt, "negative_prompt": negative_prompt, "seed": seed,
                "cut_number": i, "ckpt_name": selected_model, "width": params.get("resolution_w", 1920), "height": params.get("resolution_h", 1080),
                "steps": config.get("steps", 30), "cfg": config.get("cfg", 7.5),
                "steps": config.get("steps", 30), "cfg": config.get("cfg", 7.5),
                "sampler_name": config.get("sampler_name", "dpmpp_2m"), "scheduler": config.get("scheduler", "karras"),
                "reference_image": current_reference_image if current_reference_image else "",
                "ipadapter_file": selected_ipadapter
            })
            
            result = client.queue_prompt(workflow)
            prompt_id = result.get("prompt_id")
            if not prompt_id:
                yield create_sse_event({"type": "log", "message": f"⚠️ [Cut {i}] 큐 추가 실패"})
                continue

            max_wait = 120
            start_time = time.time()
            output_image_path = None
            
            while time.time() - start_time < max_wait:
                history = client.get_history(prompt_id)
                if prompt_id in history:
                    outputs = history[prompt_id].get("outputs", {})
                    for node_id, node_output in outputs.items():
                        if "images" in node_output:
                            image_info = node_output["images"][0]
                            image_data = client.get_image(image_info["filename"], image_info.get("subfolder", ""), image_info.get("type", "output"))
                            filename = f"cut_{i:03d}_{seed}.png"
                            filepath = os.path.join(project_dir, filename)
                            with open(filepath, 'wb') as f:
                                f.write(image_data)
                            
                            if use_reference_chaining and os.path.exists(filepath):
                                if comfyui_input_dir:
                                    chain_filename = f"chain_ref_{folder_name}_{cut_number}.png"
                                    chain_path = os.path.join(comfyui_input_dir, chain_filename)
                                    try:
                                        shutil.copy(filepath, chain_path)
                                        current_reference_image = chain_filename
                                    except: pass
                            
                            output_image_path = filepath
                            
                            # Await Veo Task result if pending
                            if veo_task:
                                try:
                                    veo_resp = await veo_task
                                    veo_prompt_text = veo_resp.choices[0].message.content
                                    if current_cut:
                                        current_cut["videoPrompt"] = veo_prompt_text
                                        current_cut["veo_generated"] = True
                                        
                                    if veo_prompt_text:
                                        txt_filename = f"cut_{i:03d}_{seed}.txt"
                                        txt_filepath = os.path.join(project_dir, txt_filename)
                                        with open(txt_filepath, 'w', encoding='utf-8') as tf: tf.write(veo_prompt_text)
                                except Exception as e:
                                    print(f"Veo Task Wait Error: {e}")

                            generated_images.append(filename)
                            
                            with open(filepath, "rb") as img_file:
                                b64_data = base64.b64encode(img_file.read()).decode('utf-8')
                                yield create_sse_event({"type": "preview", "image": f"data:image/png;base64,{b64_data}", "cutIndex": i})
                            
                            yield create_sse_event({"type": "log", "message": f"✅ [Cut {i}] 생성 완료: {filename}"})
                            client.free_memory()
                    break
                await asyncio.sleep(1)
            
            if not output_image_path:
                yield create_sse_event({"type": "log", "message": f"⚠️ [Cut {i}] 시간 초과"})
        except Exception as e:
            yield create_sse_event({"type": "log", "message": f"⚠️ [Cut {i}] 에러: {str(e)}"})
            await asyncio.sleep(1)

    # Finalize
    first_image_encoded = urllib.parse.quote(generated_images[0]) if generated_images else ""
    final_cuts_metadata = []
    for i, cut in enumerate(cuts_data):
        prefix = f"cut_{i:03d}_"
        matching_img = next((img for img in generated_images if img.startswith(prefix)), None)
        
        # Always save metadata, even if image wasn't generated
        cut_copy = cut.copy()
        cut_copy["filename"] = matching_img if matching_img else ""
        final_cuts_metadata.append(cut_copy)

    result_data = {
        "title": params['selected_title'] or topic,
        "mode": params['mode_name'],
        "resolution": f"{params['resolution_w']}x{params['resolution_h']}",
        "cuts": len(cuts_data), # Total planned cuts
        "created_at": get_time(),
        "cuts_data": final_cuts_metadata,
        "folder_name": folder_name,
        "completed": True
    }
    
    with open(os.path.join(project_dir, "metadata.json"), 'w', encoding='utf-8') as f:
        json.dump(result_data, f, indent=4, ensure_ascii=False)
        
    yield create_sse_event({"type": "done", "result": result_data})
    generation_state["status"] = "idle"
