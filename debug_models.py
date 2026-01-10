import sys
import asyncio
import json
import os

# Context setup
sys.path.append(os.path.join(os.getcwd(), 'backend'))

try:
    from comfyui_client import ComfyUIClient
except ImportError:
    # Try adding just 'backend' if above failed or running from inside backend
    sys.path.append(os.getcwd())
    from backend.comfyui_client import ComfyUIClient
except ImportError:
    print("Could not import ComfyUIClient. Make sure you are in the project root.")
    sys.exit(1)

def main():
    server_address = "127.0.0.1:8188"
    client = ComfyUIClient(server_address)
    
    print(f"Connecting to ComfyUI at {server_address}...")
    
    try:
        # Get Object Info for CheckpointLoaderSimple
        info = client.get_object_info("CheckpointLoaderSimple")
        
        if 'CheckpointLoaderSimple' not in info:
            print("❌ CheckpointLoaderSimple node not found in Object Info.")
            return

        input_req = info['CheckpointLoaderSimple'].get('input', {}).get('required', {})
        ckpt_names = input_req.get('ckpt_name', [])
        
        if not ckpt_names:
            print("❌ 'ckpt_name' input not found.")
        elif not isinstance(ckpt_names[0], list):
             print(f"❌ Unexpected format for ckpt_name: {ckpt_names}")
        else:
            models = ckpt_names[0]
            print(f"✅ Found {len(models)} models:")
            for m in models:
                print(f"  - {m}")
                
    except Exception as e:
        print(f"❌ Failed to query ComfyUI: {e}")

    # Check local config and paths
    try:
        config_path = os.path.join(os.getcwd(), 'backend', 'config.json')
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8-sig') as f:
                config = json.load(f)
            
            comfy_path = config.get("comfyui_path", "")
            print(f"\n📂 Local Config ComfyUI Path: '{comfy_path}'")
            
            if comfy_path and os.path.exists(comfy_path):
                check_dirs = [
                    os.path.join(comfy_path, "models", "checkpoints"),
                    os.path.join(comfy_path, "models", "diffusion_models")
                ]
                for d in check_dirs:
                    if os.path.exists(d):
                        print(f"  - Scanning {d}...")
                        files = os.listdir(d)
                        models = [f for f in files if f.endswith(('.safetensors', '.ckpt'))]
                        print(f"    Found {len(models)} files: {models[:5]}...")
                    else:
                        print(f"  - Directory not found: {d}")
            else:
                 print("  ⚠️ ComfyUI path not set or does not exist.")
        else:
             print("❌ backend/config.json not found.")
    except Exception as e:
        print(f"❌ Failed to inspect local config: {e}")

if __name__ == "__main__":
    main()
