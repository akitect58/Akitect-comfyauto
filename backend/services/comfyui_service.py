import os
import json
import socket
import copy
from typing import List
from backend.core.paths import BASE_DIR
from backend.comfyui_client import ComfyUIClient

def check_comfyui_connection(host="127.0.0.1", port=8188):
    """Check if ComfyUI server is reachable"""
    try:
        with socket.create_connection((host, int(port)), timeout=1):
            return True
    except (socket.timeout, ConnectionRefusedError):
        return False
    except Exception:
        return False

async def fetch_available_models(config: dict) -> List[str]:
    """
    Get list of models.
    Priority: 
    1. ComfyUI API (Object Info -> CheckpointLoaderSimple)
    2. Local Scan (if configured path exists)
    """
    # 1. Try API
    if check_comfyui_connection():
        try:
            client = ComfyUIClient("127.0.0.1:8188")
            info = client.get_object_info("CheckpointLoaderSimple")
            # Structure: {'CheckpointLoaderSimple': {'input': {'required': {'ckpt_name': [['model1.safetensors', ...], ...]}}}}
            if 'CheckpointLoaderSimple' in info:
                input_req = info['CheckpointLoaderSimple'].get('input', {}).get('required', {})
                ckpt_names = input_req.get('ckpt_name', [])
                if ckpt_names and isinstance(ckpt_names[0], list):
                    return ckpt_names[0]
        except Exception as e:
            print(f"Failed to fetch models via API: {e}")

    # 2. Try Local Scan
    comfy_path = config.get("comfyui_path", "")
    print(f"[DEBUG] Scanning for models. Configured Path: '{comfy_path}'")
    
    if comfy_path and os.path.exists(comfy_path):
        # Common paths: models/checkpoints, models/diffusion_models
        # User requested: models/diffusion_models specifically, but typically checkpoints are in models/checkpoints
        # We will scan both.
        models = []
        search_paths = [
            os.path.join(comfy_path, "models", "checkpoints"),
            os.path.join(comfy_path, "ComfyUI", "models", "checkpoints"), # Common if path is root
            os.path.join(comfy_path, "models", "diffusion_models"),
        ]
        
        for p in search_paths:
            print(f"[DEBUG] Checking path: '{p}' (Exists: {os.path.exists(p)})")
            if os.path.exists(p):
                for root, dirs, files in os.walk(p):
                    for file in files:
                        if file.endswith((".safetensors", ".ckpt")):
                            try:
                                rel = os.path.relpath(os.path.join(root, file), p)
                                models.append(rel)
                            except:
                                models.append(file)
        
        # Dedup and sort
        found_models = sorted(list(set(models)))
        print(f"[DEBUG] Found {len(found_models)} models: {found_models[:5]}...")
        return found_models

    return []

async def fetch_available_ipadapters(config: dict) -> List[str]:
    """Get list of IPAdapter models from ComfyUI API"""
    if check_comfyui_connection():
        try:
            client = ComfyUIClient("127.0.0.1:8188")
            info = client.get_object_info("IPAdapterModelLoader")
            if 'IPAdapterModelLoader' in info:
                input_req = info['IPAdapterModelLoader'].get('input', {}).get('required', {})
                models = input_req.get('ipadapter_file', [])
                if models and isinstance(models[0], list):
                    return models[0]
        except Exception as e:
            print(f"Failed to fetch IPAdapters: {e}")
            
    # Local scan fallback could go here, but API is reliable for Node lists
    return []

def load_workflow_template(workflow_name: str) -> dict:
    """Load a ComfyUI workflow template from the workflows directory"""
    workflow_path = os.path.join(BASE_DIR, "workflows", f"{workflow_name}.json")
    if os.path.exists(workflow_path):
        with open(workflow_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def prepare_workflow(template: dict, replacements: dict) -> dict:
    """Replace placeholder strings in workflow JSON safely"""
    workflow = copy.deepcopy(template)
    
    # 1. Direct replacements in nodes (Model, Seed, etc.)
    target_model = replacements.get("ckpt_name")
    target_seed = replacements.get("seed")
    target_width = replacements.get("width")
    target_height = replacements.get("height")
    target_steps = replacements.get("steps")
    target_cfg = replacements.get("cfg")
    target_sampler = replacements.get("sampler_name")
    target_scheduler = replacements.get("scheduler")
    
    for node_id, node in workflow.items():
        inputs = node.get("inputs", {})
        
        # Replace Model
        if target_model and node.get("class_type") == "CheckpointLoaderSimple":
            inputs["ckpt_name"] = target_model
            
        # Replace Dimensions (EmptyLatentImage)
        if node.get("class_type") == "EmptyLatentImage":
            if target_width: inputs["width"] = target_width
            if target_height: inputs["height"] = target_height

        # Replace Sampler Parameters (KSampler)
        if node.get("class_type") == "KSampler":
            if target_steps: inputs["steps"] = target_steps
            if target_cfg: inputs["cfg"] = target_cfg
            if target_sampler: inputs["sampler_name"] = target_sampler
            if target_scheduler: inputs["scheduler"] = target_scheduler
            if target_seed is not None: inputs["seed"] = target_seed
            
        # Replace placeholders in any string input
        for key, value in inputs.items():
            if isinstance(value, str):
                for rk, rv in replacements.items():
                    placeholder = f"{rk.upper()}_PLACEHOLDER"
                    if placeholder in value:
                        inputs[key] = value.replace(placeholder, str(rv))
                        
    return workflow

def calculate_parameters(mode: str, concept: str, cuts: int, selected_title: str = ""):
    is_long = mode.lower() == "long" or "long form" in mode.lower()
    
    params = {
        "resolution_w": 1920 if is_long else 1080,
        "resolution_h": 1080 if is_long else 1920,
        "mode_name": "LONG_FORM" if is_long else "SHORT_FORM",
        "total_cuts": cuts,
        "concept": concept,
        "image_filename": "animal_protagonist_wide.png" if is_long else "animal_protagonist_tall.png",
        "selected_title": selected_title
    }
    
    if concept == "대서사시 (Epic)":
        params["batch_loop_count"] = 5
        params["cut_instruction"] = f"{cuts}컷의 웅장한 서사시 생성"
    elif concept == "바이럴 (Viral)":
        params["batch_loop_count"] = 2
        params["cut_instruction"] = f"{cuts}컷의 트렌디하고 빠른 템포 바이럴 비디오 생성"
    else:
        params["batch_loop_count"] = 3
        
    return params
