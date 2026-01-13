import os
import shutil
import platform
import subprocess
import urllib.parse
from fastapi import APIRouter
from fastapi.responses import FileResponse
from backend.core.paths import OUTPUTS_DIR
from backend.services.openai_service import generate_veo_prompts_for_history

router = APIRouter(prefix="/api/history", tags=["history"])

@router.get("")
async def get_history():
    """Get list of generated projects"""
    projects = []
    if not os.path.exists(OUTPUTS_DIR):
        return {"projects": []}
        
    for name in os.listdir(OUTPUTS_DIR):
        path = os.path.join(OUTPUTS_DIR, name)
        if os.path.isdir(path):
            # Try to read metadata
            meta_path = os.path.join(path, "metadata.json")
            if os.path.exists(meta_path):
                import json
                try:
                    with open(meta_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if "created_at" in data and "timestamp" not in data:
                            data["timestamp"] = data["created_at"]
                        data["folder_name"] = name
                        data["id"] = name
                        
                        # Find first image for thumbnail
                        data["thumbnails"] = []
                        for img in os.listdir(path):
                            if img.endswith(('.png', '.jpg')) and "reference" not in img and "chain" not in img:
                                data["thumbnails"].append(f"/outputs/{name}/{img}")
                                break
                                
                        projects.append(data)
                except: pass
    
    # Sort by creation time desc
    projects.sort(key=lambda x: x.get("folder_name", ""), reverse=True)
    return {"projects": projects}

@router.post("/{folder_name}/title")
async def update_project_title(folder_name: str, req: dict):
    from backend.core.paths import OUTPUTS_DIR
    import json
    
    folder_name = urllib.parse.unquote(folder_name)
    path = os.path.join(OUTPUTS_DIR, folder_name)
    meta_path = os.path.join(path, "metadata.json")
    
    if os.path.exists(meta_path):
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            data["title"] = req.get("title", data.get("title"))
            
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
                
            return {"success": True, "title": data["title"]}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    return {"success": False, "error": "Not found"}

@router.get("/{folder_name}")
async def get_project_details(folder_name: str):
    folder_name = urllib.parse.unquote(folder_name)
    path = os.path.join(OUTPUTS_DIR, folder_name)
    meta_path = os.path.join(path, "metadata.json")
    
    if os.path.exists(meta_path):
        import json
        with open(meta_path, 'r', encoding='utf-8') as f:
            meta_data = json.load(f)

        # Collect assets (images)
        assets = []
        if os.path.exists(path):
            # Sort files to ensure order (e.g. cut_001, cut_002)
            sorted_files = sorted(os.listdir(path))
            for f_name in sorted_files:
                if f_name.lower().endswith(('.png', '.jpg', '.jpeg')) and "reference" not in f_name and "chain" not in f_name:
                     assets.append(f"/outputs/{folder_name}/{f_name}")

        return {
            "title": meta_data.get("title", folder_name),
            "folder_name": folder_name,
            "assets": assets,
            "metadata": meta_data
        }
    return {"error": "Not found"}

@router.delete("/{folder_name}")
async def delete_project(folder_name: str):
    folder_name = urllib.parse.unquote(folder_name)
    path = os.path.join(OUTPUTS_DIR, folder_name)
    if os.path.exists(path):
        shutil.rmtree(path)
        return {"success": True}
    return {"success": False, "error": "Not found"}

@router.get("/{folder_name}/download")
async def download_project(folder_name: str):
    folder_name = urllib.parse.unquote(folder_name)
    path = os.path.join(OUTPUTS_DIR, folder_name)
    if not os.path.exists(path):
        return {"error": "Project not found"}
        
    # Zip it
    zip_filename = f"{folder_name}.zip"
    zip_path = os.path.join(OUTPUTS_DIR, zip_filename)
    
    shutil.make_archive(zip_path.replace('.zip', ''), 'zip', path)
    
    return FileResponse(zip_path, filename=zip_filename, media_type='application/zip')

@router.get("/{folder_name}/open")
async def open_project_folder_get(folder_name: str):
    folder_name = urllib.parse.unquote(folder_name)
    path = os.path.join(OUTPUTS_DIR, folder_name)
    
    if os.path.exists(path):
        if platform.system() == "Windows":
            os.startfile(path)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
        return {"success": True}
    return {"success": False, "error": "Path not found"}

@router.post("/open-folder")
async def open_project_folder(req: dict):
    folder_path = req.get("path")
    if not folder_path: return {"success": False}
    
    # If path is relative to outputs, resolve it
    if not os.path.isabs(folder_path):
         # Try logic
         if "outputs" in folder_path:
             folder_path = os.path.join(OUTPUTS_DIR, folder_path.split("outputs/")[-1])
    
    if os.path.exists(folder_path):
        if platform.system() == "Windows":
            os.startfile(folder_path)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", folder_path])
        else:
            subprocess.Popen(["xdg-open", folder_path])
        return {"success": True}
    return {"success": False, "error": "Path not found"}

@router.post("/{folder_name}/generate_veo_prompts")
async def generate_veo_route(folder_name: str):
    return await generate_veo_prompts_for_history(folder_name)
