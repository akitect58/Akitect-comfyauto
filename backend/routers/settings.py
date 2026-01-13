from fastapi import APIRouter
from backend.core.schemas import SettingsUpdate
from backend.core.config import load_config, save_config
from backend.services.comfyui_service import fetch_available_models, check_comfyui_connection

router = APIRouter(prefix="/api/settings", tags=["settings"])

@router.get("")
async def get_settings():
    """Get current settings (API key masked)"""
    try:
        config = load_config()
        key = config.get("openai_api_key", "")
        masked_key = key[:8] + "..." + key[-4:] if len(key) > 12 else "****" if key else ""
        
        return {
            "openai_api_key_masked": masked_key,
            "openai_api_key_set": bool(key),
            "comfyui_path": config.get("comfyui_path", ""),
            "use_reference_image": config.get("use_reference_image", True),
            "selected_model": config.get("selected_model", ""),
            "steps": config.get("steps", 30),
            "cfg": config.get("cfg", 7.5),
            "sampler_name": config.get("sampler_name", "dpmpp_2m"),
            "scheduler": config.get("scheduler", "karras"),
            "prompts": config.get("prompts", {})
        }
    except Exception as e:
        print(f"Error loading settings: {e}")
        return {"error": str(e)}

@router.put("")
async def update_settings(settings: SettingsUpdate):
    """Update settings"""
    config = load_config()
    
    if settings.openai_api_key is not None: config["openai_api_key"] = settings.openai_api_key
    if settings.comfyui_path is not None: config["comfyui_path"] = settings.comfyui_path
    if settings.use_reference_image is not None: config["use_reference_image"] = settings.use_reference_image
    if settings.selected_model is not None: config["selected_model"] = settings.selected_model
    if settings.steps is not None: config["steps"] = settings.steps
    if settings.cfg is not None: config["cfg"] = settings.cfg
    if settings.sampler_name is not None: config["sampler_name"] = settings.sampler_name
    if settings.scheduler is not None: config["scheduler"] = settings.scheduler
    if settings.prompts is not None: config["prompts"] = settings.prompts
    
    save_config(config)
    return {"success": True}

@router.get("/models")
async def get_available_models():
    """Fetch available checkpoint models from ComfyUI or local scan"""
    config = load_config()
    models = await fetch_available_models(config)
    return {"models": models}
