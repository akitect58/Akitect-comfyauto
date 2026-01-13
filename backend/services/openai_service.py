import os
import json
import re
import asyncio
import time
from typing import List, AsyncGenerator
from openai import OpenAI
from sse_starlette.sse import EventSourceResponse

from backend.core.config import load_config, DEFAULT_PROMPTS
from backend.core.utils import clean_string, robust_parse_json
from backend.core.schemas import (
    DraftRequest, RegenerateDraftRequest, StoryRequest, 
    PrepareStoryRequest, RegenerateCutRequest, TitleRequest, 
    ParseScriptRequest
)
from backend.core.paths import OUTPUTS_DIR

# Globals (for streaming context)
temp_story_data = {}

def get_openai_client():
    """Get OpenAI client with API key from config"""
    config = load_config()
    api_key = config.get("openai_api_key")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)

async def generate_drafts(req: DraftRequest):
    client = get_openai_client()
    if not client:
        return {"success": False, "error": "OpenAI API Key is missing", "drafts": [], "source": "error"}

    try:
        config = load_config()
        system_prompt = config.get("prompts", {}).get("draft_generation", "당신은 실사 영상 스토리 작가입니다. 10가지 스토리 초안을 JSON 배열로 반환하세요.")
        
        system_prompt = system_prompt.replace("{{count}}", "10")
        system_prompt = system_prompt.replace("{{category}}", req.category or "ALL")
        system_prompt += "\n\n[중요] 모든 응답은 반드시 한국어로 작성하세요. title과 summary 모두 한국어로 작성하세요."
        
        user_input = req.customInput if req.customInput else f"카테고리: {req.category}"
        
        response = client.chat.completions.create(
            model="gpt-5-mini-2025-08-07",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ]
        )

        output_text = response.choices[0].message.content
        json_match = re.search(r'\[.*\]', output_text, re.DOTALL)
        if json_match:
            drafts = json.loads(json_match.group())
        else:
            drafts = [{"id": 1, "title": "Error parsing response", "summary": output_text[:500], "theme": "error"}]
        
        return {"success": True, "drafts": drafts, "source": "openai"}
    except Exception as e:
        return {"success": False, "drafts": [{"id": 1, "title": "API Error", "summary": str(e), "theme": "error"}], "error": str(e)}

async def generate_drafts_stream(mode: str = "long", category: str = None, customInput: str = None):
    config = load_config()
    client = get_openai_client()
    
    async def event_generator():
        if not client:
            yield {"event": "error", "data": json.dumps({"error": "OpenAI API Key is missing"})}
            return

        try:
            system_prompt = config.get("prompts", {}).get("draft_generation", "당신은 실사 영상 스토리 작가입니다. 10가지 스토리 초안을 JSON 배열로 반환하세요.")
            protagonist_prompt = config.get("prompts", {}).get("protagonist_prompt", "20대 중반의 한국인 여성")
            
            # Sanitize protagonist prompt for drafting (remove technical visuals)
            sanitized_protagonist = protagonist_prompt
            for term in ["8k", "uhd", "photorealistic", "national geographic", "style", "cinematic", "film", "grain"]:
                sanitized_protagonist = re.sub(r'\b'+term+r'\b', '', sanitized_protagonist, flags=re.IGNORECASE)
            sanitized_protagonist = sanitized_protagonist.replace(",", " ").replace("  ", " ").strip()
            
            system_prompt = system_prompt.replace("{{count}}", "10")
            system_prompt = system_prompt.replace("{{category}}", category or "ALL")
            system_prompt = system_prompt.replace("{{protagonist}}", sanitized_protagonist)
            system_prompt += "\n\n[중요] 모든 응답은 반드시 한국어로 작성하세요. title과 summary 모두 한국어로 작성하세요."
            
            user_input = customInput if customInput else f"카테고리: {category}"
            
            stream = client.chat.completions.create(
                model="gpt-5-mini-2025-08-07",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input}
                ],
                stream=True
            )
            
            full_text = ""
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    delta_text = chunk.choices[0].delta.content
                    full_text += delta_text
                    yield {"event": "delta", "data": json.dumps({"text": delta_text})}
            
            # Final Parse
            json_match = re.search(r'\[.*\]', full_text, re.DOTALL)
            if json_match:
                drafts = json.loads(json_match.group())
            else:
                drafts = [{"id": 1, "title": "Parse Error", "summary": full_text[:500], "theme": "error"}]
            yield {"event": "complete", "data": json.dumps({"drafts": drafts, "source": "openai"})}
                        
        except Exception as e:
            yield {"event": "error", "data": json.dumps({"error": str(e)})}
    
    return EventSourceResponse(event_generator())

async def generate_drafts_parallel(mode: str = "long", category: str = None, customInput: str = None):
    config = load_config()
    client = get_openai_client()
    
    async def event_generator():
        if not client:
            yield {"event": "error", "data": json.dumps({"error": "OpenAI API Key is missing"})}
            return
        
        try:
            protagonist_prompt = config.get("prompts", {}).get("protagonist_prompt", "20대 중반의 한국인 여성")
            base_prompt_template = config.get("prompts", {}).get("draft_generation", "스토리 작가입니다.")
            base_prompt_template = base_prompt_template.replace("{{protagonist}}", protagonist_prompt)
            base_prompt_template = base_prompt_template.replace("{{category}}", category or "ALL")
            
            user_input = customInput if customInput else f"카테고리: {category}"
            previous_summaries = []

            for i in range(10):
                draft_id = i + 1
                current_prompt = base_prompt_template.replace("{{count}}", "1")
                current_prompt += f"\n\n지금 생성할 초안 번호: {draft_id}/10"
                
                if previous_summaries:
                    current_prompt += "\n\n[이전에 생성된 초안들 (중복 회피용)]"
                    for idx, summary in enumerate(previous_summaries):
                        current_prompt += f"\n- {idx+1}. {summary[:100]}..."
                    current_prompt += "\n\n[지시사항] 위 안들과는 소재, 전개, 분위기가 **완전히 다른** 새로운 이야기를 만드세요."
                
                current_prompt += "\n반드시 단일 객체만 반환: {\"id\": " + str(draft_id) + ", \"title\": \"...\", \"summary\": \"...\", \"theme\": \"...\"}"
                current_prompt += "\n[중요] summary와 title 모두 한국어로 작성하세요."

                try:
                    stream = client.chat.completions.create(
                        model="gpt-5-mini-2025-08-07",
                        messages=[{"role": "system", "content": current_prompt}, {"role": "user", "content": user_input}],
                        stream=True
                    )

                    full_response = ""
                    for chunk in stream:
                        if chunk.choices[0].delta.content:
                            content = chunk.choices[0].delta.content
                            full_response += content
                            yield {"event": "delta", "data": json.dumps({"draft_id": draft_id, "text": content})}

                    json_match = re.search(r'\{.*\}', full_response, re.DOTALL)
                    if json_match:
                        draft = json.loads(json_match.group())
                        draft["id"] = draft_id
                    else:
                        draft = {"id": draft_id, "title": f"Story #{draft_id}", "summary": full_response[:400], "theme": "parsed"}
                    
                    yield {"event": "draft", "data": json.dumps(draft)}
                    previous_summaries.append(f"[{draft.get('title', 'Untitled')}] {draft.get('summary', '')}")

                except Exception as e:
                    error_draft = {"id": draft_id, "title": f"Error #{draft_id}", "summary": str(e), "theme": "error"}
                    yield {"event": "draft", "data": json.dumps(error_draft)}
                    previous_summaries.append("Error during generation")

            yield {"event": "complete", "data": json.dumps({"total": 10, "source": "openai_serial_context"})}

        except Exception as e:
            yield {"event": "error", "data": json.dumps({"error": str(e)})}
    
    return EventSourceResponse(event_generator())

async def regenerate_draft(req: RegenerateDraftRequest):
    client = get_openai_client()
    if not client:
        return {"success": False, "error": "OpenAI API Key is missing"}

    try:
        config = load_config()
        protagonist_prompt = config.get("prompts", {}).get("protagonist_prompt", "20대 중반의 한국인 여성")
        base_prompt = config.get("prompts", {}).get("draft_generation", "스토리 작가입니다.")
        base_prompt = base_prompt.replace("{{protagonist}}", protagonist_prompt)
        base_prompt = base_prompt.replace("{{category}}", req.category or "ALL")

        user_input = req.customInput if req.customInput else f"카테고리: {req.category}"

        single_prompt = base_prompt.replace("{{count}}", "1")
        single_prompt += f"\n\n지금 생성할 초안 번호: {req.draftId}/10"
        single_prompt += "\n반드시 단일 객체만 반환: {\"id\": " + str(req.draftId) + ", \"title\": \"...\", \"summary\": \"...\", \"theme\": \"...\"}"
        single_prompt += "\n[중요] summary와 title 모두 한국어로 작성하세요."

        response = client.chat.completions.create(
            model="gpt-5-mini-2025-08-07",
            messages=[{"role": "system", "content": single_prompt}, {"role": "user", "content": user_input}]
        )
        
        output_text = response.choices[0].message.content
        json_match = re.search(r'\{.*\}', output_text, re.DOTALL)
        
        if json_match:
            draft = json.loads(json_match.group())
            draft["id"] = req.draftId
        else:
            draft = {"id": req.draftId, "title": "Regeneration Error", "summary": output_text[:500], "theme": "error"}
            
        return {"success": True, "draft": draft}

    except Exception as e:
        return {"success": False, "error": str(e), "draft": {"id": req.draftId, "title": "API Error", "summary": str(e), "theme": "error"}}

async def generate_story(req: StoryRequest):
    client = get_openai_client()
    if not client:
         return {"success": False, "error": "OpenAI API Key is missing"}

    total_cuts = 100 if req.mode == "long" else 20
    config = load_config()
    
    try:
        system_prompt = config.get("prompts", {}).get("story_confirmation", "")
        if not system_prompt:
             system_prompt = DEFAULT_PROMPTS.get("story_confirmation", "")
             
        system_prompt = system_prompt.replace("{cuts}", str(total_cuts))
        system_prompt = system_prompt.replace("{{cut_count}}", str(total_cuts))
        
        # Enforce imagePrompt
        system_prompt += (
            "\n\n[중요 추가 지침] 각 컷에는 반드시 'imagePrompt' 필드를 포함하세요. "
            "'imagePrompt'는 Stable Diffusion 이미지 생성용 **상세 영문 프롬프트**입니다. "
            "예: \"A lone wolf standing on a rocky outcrop, howling at the moon, mist swirling, photorealistic, 8K UHD\""
        )
        
        user_input = (
            f"제목: {req.draftTitle}\n\n초안 요약:\n{req.draftSummary}\n\n"
            f"위 초안을 바탕으로 {total_cuts}컷의 상세 스토리와 캐릭터 묘사를 생성해주세요.\n"
            f"필수: 각 컷에 'description'(한글)과 'imagePrompt'(영문)를 모두 포함하세요."
        )
        
        response = client.chat.completions.create(
            model="gpt-5-mini-2025-08-07",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ]
        )
        
        output_text = response.choices[0].message.content
        json_match = re.search(r'\{.*\}', output_text, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
            cuts = parsed.get("cuts", [])
            character_prompt = parsed.get("characterPrompt", "A majestic wild animal (Fallback)")
        else:
            lines = output_text.split('\n')
            cuts = [{"cutNumber": i+1, "description": line[:200], "imagePrompt": f"Scene {i+1}"} for i, line in enumerate(lines[:total_cuts]) if line.strip()]
            character_prompt = "Wild Animal"
        
        return {"success": True, "totalCuts": total_cuts, "cuts": cuts, "characterPrompt": character_prompt, "source": "openai"}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def prepare_story_generation(req: PrepareStoryRequest):
    import uuid
    request_id = str(uuid.uuid4())
    temp_story_data[request_id] = {
        "draftId": req.draftId,
        "draftTitle": req.draftTitle,
        "draftSummary": req.draftSummary,
        "mode": req.mode
    }
    return {"requestId": request_id}

async def story_generation_stream(requestId: str = None, draftId: int = None, draftTitle: str = None, draftSummary: str = None, mode: str = "long"):
    if requestId and requestId in temp_story_data:
        data = temp_story_data[requestId]
        draftTitle = data["draftTitle"]
        draftSummary = data["draftSummary"]
        mode = data["mode"]
        targetCuts = data.get("targetCuts")
    
    # Default cuts if not specified
    total_cuts = targetCuts if targetCuts else (100 if mode == "long" else 20)
    chunk_size = 10
    total_chunks = (total_cuts + chunk_size - 1) // chunk_size
    
    config = load_config()
    client = get_openai_client()

    async def generate_chunk_task(chunk_idx, start_cut, end_cut, guide, context=""):
        try:
            prompt_template = config.get("prompts", {}).get("story_chunk_generation", "")
            if not prompt_template: prompt_template = DEFAULT_PROMPTS.get("story_chunk_generation")
            
            prompt = prompt_template.replace("{{story_title}}", draftTitle)
            prompt = prompt.replace("{{start_cut}}", str(start_cut))
            prompt = prompt.replace("{{end_cut}}", str(end_cut))
            prompt = prompt.replace("{{guide}}", guide)
            prompt = prompt.replace("{{context}}", context)
            prompt = prompt.replace("{{atmosphere}}", draftSummary[:200])
            prompt = prompt.replace("{{chunk_size}}", str(end_cut - start_cut + 1))
            
            user_msg = f"Generate cuts {start_cut} to {end_cut}. Guide: {guide}. Context: {context}. Output valid JSON."
            
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model="gpt-5-mini-2025-08-07",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_msg}
                ],
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            
            parsed = robust_parse_json(content)
            if not parsed:
                # print(f"[DEBUG] Chunk {chunk_idx} Parsing Failed!")
                parsed = {}
            # else:
            #      print(f"[DEBUG] Chunk {chunk_idx} Parsed Successfully. Cuts: {len(parsed.get('cuts', []))}") 

            cuts = parsed.get("cuts", [])
            
            # Post-process: ensure cut numbers are correct
            for i, cut in enumerate(cuts):
                cut["cutNumber"] = start_cut + i
                cut["characterTag"] = "The Wild Animal"
                
            return {"index": chunk_idx, "cuts": cuts, "text": f"\n[Chunk {chunk_idx+1} Done] Generated {len(cuts)} cuts.\n"}
        except Exception as e:
            return {"index": chunk_idx, "cuts": [], "text": f"\n[Chunk {chunk_idx+1} Error] {str(e)}\n", "error": str(e)}

    async def event_generator():
        if not client:
            yield {"event": "error", "data": json.dumps({"error": "OpenAI API Key is missing"})}
            return

        try:
            # Phase 1: Blueprint
            yield {"event": "delta", "data": json.dumps({"text": f"📋 Planning {total_cuts} cuts into {total_chunks} chunks...\n"})}
            
            blueprint_prompt = config.get("prompts", {}).get("story_blueprint_generation", "")
            blueprint_prompt = blueprint_prompt.replace("{{total_cuts}}", str(total_cuts))
            blueprint_prompt = blueprint_prompt.replace("{{total_chunks}}", str(total_chunks))
            blueprint_prompt = blueprint_prompt.replace("{{story_title}}", draftTitle)
            blueprint_prompt = blueprint_prompt.replace("{{story_summary}}", draftSummary)
            blueprint_prompt = blueprint_prompt.replace("{{theme}}", "Nature Drama")

            bp_response = await asyncio.to_thread(
                client.chat.completions.create,
                model="gpt-5-mini-2025-08-07",
                messages=[{"role": "system", "content": blueprint_prompt}, {"role": "user", "content": "Generate Blueprint JSON."}],
                response_format={"type": "json_object"}
            )
            bp_json = json.loads(bp_response.choices[0].message.content)
            guides = bp_json if isinstance(bp_json, list) else bp_json.get("chunks", bp_json.get("guides", []))
            
            # Fallback if parsing fails or structure varies
            if not guides or not isinstance(guides, list):
                 guides = [{"guide": "Follow general story arc."} for _ in range(total_chunks)]
            
            yield {"event": "delta", "data": json.dumps({"text": "✅ Blueprint Created. Starting Parallel Generation...\n"})}

            # Phase 2: Parallel Execution
            tasks = []
            for i in range(total_chunks):
                start = i * chunk_size + 1
                end = min((i + 1) * chunk_size, total_cuts)
                # Helper to get guide safely
                guide_text = "Follow plot."
                context_text = "Standard scene context."
                if i < len(guides):
                    guide_text = guides[i].get("guide", "Follow plot.")
                    context_text = guides[i].get("context", "Standard scene context.")
                
                tasks.append(generate_chunk_task(i, start, end, guide_text, context_text))
            
            # Stream results as they complete
            all_cuts = []
            # print(f"[DEBUG] Starting collection of {len(tasks)} chunks...")
            for future in asyncio.as_completed(tasks):
                result = await future
                # print(f"[DEBUG] Chunk {result.get('index')} finished. Cuts found: {len(result.get('cuts', []))}")
                if result.get("cuts"):
                    all_cuts.extend(result["cuts"])
                else:
                    # print(f"[DEBUG] Chunk {result.get('index')} Failed/Empty: {result.get('text')}")
                    pass
                    
                yield {"event": "delta", "data": json.dumps({"text": result["text"]})}
            
            # Phase 3: Finalize
            all_cuts.sort(key=lambda x: x["cutNumber"])
            print(f"[DEBUG] Total cuts collected: {len(all_cuts)}")
            
            full_text = "\n".join([f"{c['cutNumber']}. {c.get('description', 'No Desc')}" for c in all_cuts])
            print(f"[DEBUG] Final FullText Length: {len(full_text)}")
            
            yield {"event": "complete", "data": json.dumps({
                "cuts": all_cuts,
                "characterPrompt": "The Wild Animal",
                "fullText": full_text,
                "source": "openai_parallel"
            })}

        except Exception as e:
            yield {"event": "error", "data": json.dumps({"error": str(e)})}

    return EventSourceResponse(event_generator())

async def regenerate_cut(req: RegenerateCutRequest):
    client = get_openai_client()
    if not client:
        return {"success": False, "error": "OpenAI API Key is missing"}

    config = load_config()
    try:
        system_prompt = config.get("prompts", {}).get("single_cut_regeneration", "")
        if not system_prompt:
            system_prompt = DEFAULT_PROMPTS.get("single_cut_regeneration", "")
        
        system_prompt = system_prompt.replace("{{story_title}}", req.storyTitle)
        system_prompt = system_prompt.replace("{{character_tag}}", req.characterTag)
        system_prompt = system_prompt.replace("{{cut_number}}", str(req.cutNumber))
        system_prompt = system_prompt.replace("{{total_cuts}}", str(req.totalCuts))
        system_prompt = system_prompt.replace("{{emotion_range}}", req.emotionRange)
        
        prev_summary = req.previousCut.get("description", "N/A") if req.previousCut else "N/A"
        next_summary = req.nextCut.get("description", "N/A") if req.nextCut else "N/A"
        system_prompt = system_prompt.replace("{{previous_cut}}", prev_summary)
        system_prompt = system_prompt.replace("{{next_cut}}", next_summary)
        
        user_input = f"Regenerate cut {req.cutNumber}..."
        
        response = client.chat.completions.create(
            model="gpt-5-mini-2025-08-07",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_input}]
        )
        
        output_text = response.choices[0].message.content
        json_match = re.search(r'\{.*\}', output_text, re.DOTALL)
        if json_match:
            cut = json.loads(json_match.group())
            cut["cutNumber"] = req.cutNumber
            cut["characterTag"] = req.characterTag
        else:
            cut = {"cutNumber": req.cutNumber, "description": output_text[:200]}
            
        return {"success": True, "cut": cut, "source": "openai"}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def generate_titles(req: TitleRequest):
    client = get_openai_client()
    if not client:
        return {"success": False, "error": "OpenAI API Key is missing"}
    
    config = load_config()
    try:
        system_prompt = config.get("prompts", {}).get("title_generation", "한국어 제목 생성기")
        system_prompt += "\n\n[CRITICAL REQUEST] All titles must be in KOREAN (한국어)."
        
        response = client.chat.completions.create(
            model="gpt-5-mini-2025-08-07",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"스토리 요약:\n{req.storyPreview}"}
            ]
        )
        output_text = response.choices[0].message.content
        json_match = re.search(r'\[.*\]', output_text, re.DOTALL)
        if json_match:
            titles = json.loads(json_match.group())
        else:
            titles = [{"title": "Parse Error", "style": "general", "hook": output_text[:100]}]
            
        return {"success": True, "titles": titles, "source": "openai"}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def parse_script(req: ParseScriptRequest):
    client = get_openai_client()
    if not client:
        return {"success": False, "error": "OpenAI API Key is missing"}

    config = load_config()
    try:
        system_prompt = config.get("prompts", {}).get("script_parsing", "Parse script to cuts JSON.")
        system_prompt = system_prompt.replace("{{script}}", req.script)
        
        response = client.chat.completions.create(
            model="gpt-5-mini-2025-08-07",
            messages=[{"role": "system", "content": "You are a script parser JSON generator."}, {"role": "user", "content": system_prompt}]
        )
        output_text = response.choices[0].message.content
        json_match = re.search(r'\{.*\}', output_text, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
            return {"success": True, "totalCuts": len(parsed.get("cuts", [])), "cuts": parsed.get("cuts", []), "characterPrompt": parsed.get("characterPrompt", ""), "source": "openai"}
        else:
            return {"success": False, "error": "Parsing failed"}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def generate_veo_prompts_for_history(folder_name: str):
    import urllib.parse
    folder_name = urllib.parse.unquote(folder_name)
    folder_path = os.path.join(OUTPUTS_DIR, folder_name)
    meta_path = os.path.join(folder_path, "metadata.json")
    
    if not os.path.exists(meta_path):
        return {"success": False, "error": "Metadata not found"}
        
    config = load_config()
    client = get_openai_client()
    if not client:
        return {"success": False, "error": "OpenAI API Key is missing"}

    try:
        with open(meta_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
            
        cuts_data = metadata.get("cuts_data", [])
        updated_cuts = []
        veo_prompt_template = config.get("prompts", {}).get("veo_video", "")

        for cut in cuts_data:
            if "videoPrompt" not in cut or not cut["videoPrompt"]:
                prompt_text = veo_prompt_template
                prompt_text = prompt_text.replace("{{scene_description}}", cut.get("description", ""))
                prompt_text = prompt_text.replace("{{physics_detail}}", cut.get("physicsDetail", "None"))
                
                try:
                    response = client.chat.completions.create(
                        model="gpt-5-mini-2025-08-07",
                        messages=[{"role": "system", "content": "Fill the template strictly."}, {"role": "user", "content": prompt_text}]
                    )
                    cut["videoPrompt"] = response.choices[0].message.content.strip()
                    cut["veo_generated"] = True
                except:
                    cut["videoPrompt"] = "Gen Failed"
            
            updated_cuts.append(cut)
            
        metadata["cuts_data"] = updated_cuts
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=4, ensure_ascii=False)
            
        return {"success": True, "updated_cuts": updated_cuts}
    except Exception as e:
        return {"success": False, "error": str(e)}
        return {"success": True, "updated_cuts": updated_cuts}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def generate_veo_prompts_batch(cuts_metadata: List[dict]):
    """
    Batch generate Veo prompts for multiple cuts in one go.
    cuts_metadata: list of dicts with keys 'cutNumber', 'description', 'physicsDetail', etc.
    Returns: dict { cutIndex: prompt_string }
    """
    client = get_openai_client()
    if not client: return {}

    try:
        # Construct Batch Prompt
        descriptions_str = ""
        for cut in cuts_metadata:
            descriptions_str += f"[Cut {cut['cutNumber']}] Desc: {cut.get('description','')} | Physics: {cut.get('physicsDetail','')} | Emotion: {cut.get('emotionLevel','')}\n"

        system_prompt = (
            "You are a Video Prompt Expert for Google Veo 3.1.\n"
            "Generate optimized video prompts for the list of scenes provided.\n"
            "Return ONLY a JSON Object with a key 'prompts' which is a list of objects: {\"cutNumber\": int, \"videoPrompt\": \"...\"}\n"
            "Each videoPrompt must include visual style, camera movement, and lighting details."
        )

        response = await asyncio.to_thread(
            client.chat.completions.create,
            model="gpt-5-mini-2025-08-07",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": descriptions_str}
            ],
            response_format={"type": "json_object"}
        )
        
        content = response.choices[0].message.content
        parsed = robust_parse_json(content)
        
        result_map = {}
        if parsed and "prompts" in parsed:
            for item in parsed["prompts"]:
                result_map[item["cutNumber"]] = item["videoPrompt"]
        
        return result_map
    except Exception as e:
        print(f"Batch Veo Generation Error: {e}")
        return {}
