import websocket
import uuid
import json
import urllib.request
import urllib.parse
from openai import OpenAI

# ComfyUI API Client
class ComfyUIClient:
    def __init__(self, server_address):
        self.server_address = server_address
        self.client_id = str(uuid.uuid4())

    def queue_prompt(self, prompt):
        p = {"prompt": prompt, "client_id": self.client_id}
        data = json.dumps(p).encode('utf-8')
        req = urllib.request.Request("http://{}/prompt".format(self.server_address), data=data)
        return json.loads(urllib.request.urlopen(req).read())

    def get_image(self, filename, subfolder, folder_type):
        data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
        url_values = urllib.parse.urlencode(data)
        with urllib.request.urlopen("http://{}/view?{}".format(self.server_address, url_values)) as response:
            return response.read()

    def get_history(self, prompt_id):
        with urllib.request.urlopen("http://{}/history/{}".format(self.server_address, prompt_id)) as response:
            return json.loads(response.read())

    def upload_image(self, image_data, filename="reference.png", subfolder="inputs", overwrite=True):
        """Upload image to ComfyUI input directory"""
        # Note: ComfyUI upload API expects multipart/form-data.
        # implementation simplified for now; assumes we save file locally to ComfyUI input folder if on same machine,
        # or implement full multipart upload if remote. 
        # Since user said "Local", we might just copy the file if paths are accessible, 
        # BUT standardized API upload is safer.
        
        # multipart upload implementation
        import requests
        files = {'image': (filename, image_data)}
        data = {'overwrite': str(overwrite).lower(), 'subfolder': subfolder}
        response = requests.post(
            "http://{}/upload/image".format(self.server_address),
            files=files,
            data=data
        )
        return response.json()

    def connect_websocket(self, ws_url):
        ws = websocket.WebSocket()
        ws.connect(ws_url.format(self.client_id))
        return ws
