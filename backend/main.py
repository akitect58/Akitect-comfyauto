import time
import asyncio
import os
import json
import shutil
import random
import re
from typing import AsyncGenerator, List, Dict
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI

app = FastAPI()

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

if not os.path.exists(OUTPUTS_DIR):
    os.makedirs(OUTPUTS_DIR)

# Config helpers
def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"openai_api_key": "", "comfyui_path": "", "prompts": {}}

def save_config(config):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=4)

def get_openai_client():
    """Get OpenAI client with API key from config"""
    config = load_config()
    api_key = config.get("openai_api_key", "")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)

# Serve assets & outputs
app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")
app.mount("/outputs", StaticFiles(directory=OUTPUTS_DIR), name="outputs")

# ==========================================
# [Mock Data] Multi-Step Workflow
# ==========================================
CATEGORIES = ["사고", "자연재해", "보은", "미스터리", "서바이벌", "로맨스", "우정", "복수", "성장", "모험"]

MOCK_DRAFTS = {
    "사고": [
        {"id": 1, "title": "The Last Witness", "summary": "이른 아침 출근길, 한 여성이 끔찍한 교통사고를 목격한다. 그녀가 본 것은 단순한 사고가 아니었다. 블랙박스에 담긴 진실, 그리고 사라진 운전자. 모든 증거가 그녀를 가리킬 때, 진짜 범인을 찾기 위한 48시간의 추격이 시작된다.", "theme": "thriller"},
        {"id": 2, "title": "Broken Promises", "summary": "10년 전 그날의 사고로 모든 것을 잃은 남자. 가해자는 법의 허점을 이용해 무죄로 풀려났다. 이제 그는 잊혀진 사건의 진실을 파헤치며, 자신만의 정의를 실현하려 한다. 하지만 진실은 그가 예상한 것보다 훨씬 잔인했다.", "theme": "drama"},
        {"id": 3, "title": "Miracle Mile", "summary": "고속도로 위 100중 추돌 사고. 그 혼란 속에서 한 응급구조사가 자신의 목숨을 걸고 생존자들을 구해낸다. 모두가 포기한 순간, 그녀는 왜 달려들었을까? 사고 현장에서 펼쳐지는 인간 본성의 극한.", "theme": "heroic"},
        {"id": 4, "title": "Chain Reaction", "summary": "한 건의 사소한 접촉 사고가 도시 전체를 마비시킨다. 연쇄적으로 일어나는 사건들, 그리고 우연히 얽힌 다섯 사람의 운명. 그들은 서로를 구할 수 있을까, 아니면 함께 추락할 것인가?", "theme": "ensemble"},
        {"id": 5, "title": "The Survivor", "summary": "해저 터널 붕괴 사고에서 홀로 살아남은 청년. 트라우마와 생존자 죄책감에 시달리던 그에게 한 통의 전화가 걸려온다. '당신이 살아남은 건 우연이 아닙니다.' 사고의 진짜 원인을 추적하는 그의 위험한 여정.", "theme": "mystery"},
        {"id": 6, "title": "Intersection", "summary": "같은 교차로, 같은 시간, 다른 인생. 교통사고로 만난 두 사람이 서로의 삶을 바꿔놓는다. 가해자와 피해자, 그 경계가 무너질 때 남는 것은 무엇일까? 용서와 속죄에 관한 깊은 이야기.", "theme": "emotional"},
        {"id": 7, "title": "Impact Zone", "summary": "항공기 추락 사고 현장. 생존자는 없다고 발표되었지만, 한 기자가 잔해 속에서 이상한 점을 발견한다. 블랙박스가 조작되었다? 은폐된 진실을 파헤치는 탐사보도의 여정.", "theme": "investigative"},
        {"id": 8, "title": "Second Chance", "summary": "음주운전 사고로 타인의 삶을 망친 남자. 5년의 복역 후 출소한 그는 피해자 가족을 찾아간다. 용서받을 수 없는 죄, 그럼에도 속죄의 길을 걷는 한 인간의 고통스러운 여정.", "theme": "redemption"},
        {"id": 9, "title": "Edge of Impact", "summary": "스턴트맨으로 살아온 그에게 사고는 일상이었다. 하지만 이번 사고는 달랐다. 카메라 앞에서 일어난 '사고'는 계획된 살인이었다. 진실을 증명할 수 있는 건 오직 그의 기억뿐.", "theme": "action"},
        {"id": 10, "title": "After the Crash", "summary": "스쿨버스 전복 사고에서 아이들을 모두 구한 젊은 교사. 영웅으로 칭송받지만, 그녀의 마음속에는 구하지 못한 단 한 명의 얼굴이 사라지지 않는다. 죄책감과 트라우마를 극복하는 치유의 이야기.", "theme": "healing"}
    ],
    "자연재해": [
        {"id": 1, "title": "The Day Earth Shook", "summary": "규모 9.1 초대형 지진이 도시를 덮친다. 무너진 빌딩 잔해 속, 엘리베이터에 갇힌 다섯 사람의 72시간 생존기. 그들은 서로가 유일한 희망이다.", "theme": "survival"},
        {"id": 2, "title": "Rising Waters", "summary": "기록적인 폭우가 마을을 삼킨다. 고립된 작은 마을에서 주민들은 힘을 합쳐 살아남아야 한다. 물이 차오르는 속도보다 빠르게, 그들의 연대도 커져간다.", "theme": "community"},
        {"id": 3, "title": "Eye of the Storm", "summary": "카테고리 5 허리케인이 접근 중. 대피 명령을 무시하고 남은 한 기상학자. 그녀에게는 폭풍의 눈을 관측해야만 하는 이유가 있었다.", "theme": "scientific"},
        {"id": 4, "title": "Frozen World", "summary": "예고 없이 찾아온 빙하기. 영하 60도의 극한 추위 속에서 살아남기 위한 가족의 사투. 마지막 따뜻함을 나눌 수 있을 것인가.", "theme": "family"},
        {"id": 5, "title": "When Mountains Fall", "summary": "산사태가 마을을 덮친 그날 밤. 구조대가 도착하기 전까지 버텨야 하는 생존자들. 흙더미 아래에서 들려오는 희미한 목소리가 그들을 이끈다.", "theme": "rescue"},
        {"id": 6, "title": "The Volcano's Wrath", "summary": "휴화산이 갑자기 폭발한다. 용암이 마을을 향해 흘러오는 가운데, 한 소방관은 자신의 모든 것을 걸고 주민들을 대피시킨다.", "theme": "heroic"},
        {"id": 7, "title": "Tsunami Hour", "summary": "해안가 리조트에서 행복한 휴가를 보내던 가족. 갑자기 바다가 물러가고, 30분 후 거대한 파도가 몰려온다. 생존을 위한 절박한 선택의 순간들.", "theme": "disaster"},
        {"id": 8, "title": "Buried Alive", "summary": "눈사태에 매몰된 스키어. 눈 속에서 보내는 8시간, 그의 머릿속을 스쳐가는 삶의 기억들. 그리고 구조대의 삽 소리가 들려올 때.", "theme": "introspective"},
        {"id": 9, "title": "Wildfire", "summary": "통제 불능의 산불이 캘리포니아를 집어삼킨다. 소방관들의 사투, 그리고 모든 것을 잃은 사람들의 재건 이야기.", "theme": "devastation"},
        {"id": 10, "title": "After the Quake", "summary": "지진 이후 3일째. 무너진 병원 지하에 갇힌 의사와 환자들. 제한된 의료품으로 생명을 살려야 하는 극한 상황.", "theme": "medical"}
    ]
}

# 나머지 카테고리에 기본 초안 생성
for cat in CATEGORIES:
    if cat not in MOCK_DRAFTS:
        MOCK_DRAFTS[cat] = [
            {"id": i+1, "title": f"{cat} Story {i+1}", "summary": f"{cat}를 주제로 한 흥미진진한 이야기 #{i+1}. 예상치 못한 전개와 감동적인 결말이 기다리고 있습니다.", "theme": "general"}
            for i in range(10)
        ]

MOCK_TITLES = [
    {"title": "Against All Odds", "style": "impact"},
    {"title": "A Fleeting Hope", "style": "emotional"},
    {"title": "The Great Escape", "style": "impact"},
    {"title": "Whispers in the Rain", "style": "emotional"},
    {"title": "Wild Heart: A Survivor's Tale", "style": "documentary"},
    {"title": "The Urban Survivor", "style": "documentary"},
    {"title": "Breaking Point", "style": "impact"},
    {"title": "Into the Unknown", "style": "emotional"},
    {"title": "Unbreakable Spirit", "style": "impact"},
    {"title": "The Last Stand", "style": "documentary"}
]

# ==========================================
# [API] Settings
# ==========================================

class SettingsUpdate(BaseModel):
    openai_api_key: str | None = None
    comfyui_path: str | None = None
    prompts: dict | None = None

@app.get("/api/settings")
async def get_settings():
    """Get current settings (API key masked)"""
    config = load_config()
    # Mask API key for security
    masked_key = ""
    if config.get("openai_api_key"):
        key = config["openai_api_key"]
        masked_key = key[:8] + "..." + key[-4:] if len(key) > 12 else "****"
    return {
        "openai_api_key_masked": masked_key,
        "openai_api_key_set": bool(config.get("openai_api_key")),
        "comfyui_path": config.get("comfyui_path", ""),
        "prompts": config.get("prompts", {})
    }

@app.put("/api/settings")
async def update_settings(settings: SettingsUpdate):
    """Update settings"""
    config = load_config()
    
    if settings.openai_api_key is not None:
        config["openai_api_key"] = settings.openai_api_key
    if settings.comfyui_path is not None:
        config["comfyui_path"] = settings.comfyui_path
    if settings.prompts is not None:
        config["prompts"] = settings.prompts
    
    save_config(config)
    return {"success": True}

# ==========================================
# [API] Workflow Endpoints
# ==========================================

class DraftRequest(BaseModel):
    mode: str  # "long" or "short"
    category: str | None = None
    customInput: str | None = None

class StoryRequest(BaseModel):
    mode: str
    draftId: int
    draftTitle: str
    draftSummary: str

class UploadRequest(BaseModel):
    image: str # Base64 string
    filename: str

class TitleRequest(BaseModel):
    storyPreview: str

@app.post("/api/workflow/upload_reference")
async def upload_reference(req: UploadRequest):
    """Upload reference image for IP-Adapter"""
    try:
        # Decode base64
        import base64
        image_data = base64.b64decode(req.image.split(",")[1])
        
        # Save locally to assets/temp (just for serving back to frontend if needed)
        # And upload to ComfyUI
        
        # For this implementation, we assume ComfyUI is local or standard API upload
        # If local, we can just save it to ComfyUI input folder if path is known from config
        config = load_config()
        comfy_path = config.get("comfyui_path", "")
        
        if comfy_path and os.path.exists(comfy_path):
            input_dir = os.path.join(comfy_path, "input")
            if not os.path.exists(input_dir):
                os.makedirs(input_dir)
            with open(os.path.join(input_dir, req.filename), "wb") as f:
                f.write(image_data)
            return {"success": True, "path": req.filename, "method": "local_copy"}
        
        # If remote or path not set, use ComfyUI API to upload (TODO: Implement full API upload)
        # For now, just save to local assets so frontend shows it
        temp_path = os.path.join(ASSETS_DIR, req.filename)
        with open(temp_path, "wb") as f:
            f.write(image_data)
            
        return {"success": True, "path": f"/assets/{req.filename}", "method": "temp_server"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/workflow/drafts")
async def generate_drafts(req: DraftRequest):
    """Step 1: Generate 10 story drafts based on category or custom input"""
    config = load_config()
    client = get_openai_client()
    
    # If no API key, use mock data
    if not client:
        await asyncio.sleep(1.5)
        if req.category and req.category in MOCK_DRAFTS:
            drafts = MOCK_DRAFTS[req.category]
        else:
            input_text = req.customInput or "custom story"
            drafts = [
                {"id": i+1, "title": f"Version {i+1}: {input_text[:20]}...", "summary": f"사용자가 입력한 '{input_text}'를 기반으로 한 실사 스토리 버전 {i+1}. AI가 창의적으로 해석하여 독특한 전개를 구성했습니다.", "theme": "custom"}
                for i in range(10)
            ]
        return {"success": True, "drafts": drafts, "source": "mock"}
    
    # Real OpenAI API call
    try:
        system_prompt = config.get("prompts", {}).get("draft_generation", "당신은 실사 영상 스토리 작가입니다. 10가지 스토리 초안을 JSON 배열로 반환하세요.")
        user_input = req.customInput if req.customInput else f"카테고리: {req.category}"
        
        response = client.responses.create(
            model="gpt-5.2",
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ]
        )
        
        # Parse JSON from response
        output_text = response.output_text
        # Try to extract JSON array from response
        json_match = re.search(r'\[.*\]', output_text, re.DOTALL)
        if json_match:
            drafts = json.loads(json_match.group())
        else:
            drafts = [{"id": 1, "title": "Error parsing response", "summary": output_text[:500], "theme": "error"}]
        
        return {"success": True, "drafts": drafts, "source": "openai"}
    except Exception as e:
        # Fallback to mock on error
        print(f"OpenAI Error: {e}")
        if req.category and req.category in MOCK_DRAFTS:
            drafts = MOCK_DRAFTS[req.category]
        else:
            drafts = [{"id": 1, "title": "API Error", "summary": str(e), "theme": "error"}]
        return {"success": True, "drafts": drafts, "source": "mock_fallback", "error": str(e)}

@app.post("/api/workflow/story")
async def generate_story(req: StoryRequest):
    """Step 2: Generate detailed story cuts and character description"""
    config = load_config()
    client = get_openai_client()
    total_cuts = 100 if req.mode == "long" else 20
    
    # If no API key, use mock data
    if not client:
        await asyncio.sleep(2)
        cuts = []
        cut_descriptions = [
            "이른 새벽, 안개가 자욱한 도로. 희미한 가로등 불빛 아래 한 여성이 걸어간다.",
            "갑작스러운 충돌음. 그녀의 눈이 커지며 고개를 돌린다.",
            "사고 현장. 뒤틀린 금속과 흩어진 유리 파편들.",
            "떨리는 손으로 휴대폰을 꺼내는 그녀. 119를 누르지만 손가락이 굳어버린다.",
            "멀리서 다가오는 인영. 누군가 사고 현장을 떠나고 있다.",
        ]
        for i in range(1, total_cuts + 1):
            cuts.append({"cutNumber": i, "description": cut_descriptions[(i - 1) % len(cut_descriptions)] + f" (컷 {i})"})
        
        character_prompt = "[Mock] 메인 캐릭터 - 30대 초반 한국인 여성, 단발 머리"
        return {"success": True, "totalCuts": total_cuts, "cuts": cuts, "characterPrompt": character_prompt, "source": "mock"}
    
    # Real OpenAI API call
    try:
        system_prompt = config.get("prompts", {}).get("story_confirmation", "")
        if not system_prompt:
            system_prompt = f"당신은 영상 제작 전문 시나리오 작가입니다. {total_cuts}컷의 상세 스토리를 JSON으로 반환하세요."
        else:
            system_prompt = system_prompt.replace("{cuts}", str(total_cuts))
        
        user_input = f"제목: {req.draftTitle}\n\n초안 요약:\n{req.draftSummary}\n\n위 초안을 바탕으로 {total_cuts}컷의 상세 스토리와 캐릭터 묘사를 생성해주세요."
        
        response = client.responses.create(
            model="gpt-5.2",
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ]
        )
        
        output_text = response.output_text
        
        # Try to parse JSON
        json_match = re.search(r'\{.*\}', output_text, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
            cuts = parsed.get("cuts", [])
            character_prompt = parsed.get("characterPrompt", "캐릭터 정보 없음")
        else:
            # Fallback: create simple cuts from text
            lines = output_text.split('\n')
            cuts = [{"cutNumber": i+1, "description": line[:200]} for i, line in enumerate(lines[:total_cuts]) if line.strip()]
            character_prompt = "응답에서 캐릭터 정보를 파싱하지 못했습니다."
        
        return {"success": True, "totalCuts": total_cuts, "cuts": cuts, "characterPrompt": character_prompt, "source": "openai"}
    except Exception as e:
        print(f"OpenAI Story Error: {e}")
        cuts = [{"cutNumber": 1, "description": f"API 오류: {str(e)}"}]
        return {"success": True, "totalCuts": 1, "cuts": cuts, "characterPrompt": str(e), "source": "error"}

@app.post("/api/workflow/titles")
async def generate_titles(req: TitleRequest):
    """Step 4: Generate native English title suggestions"""
    config = load_config()
    client = get_openai_client()
    
    # If no API key, use mock data
    if not client:
        await asyncio.sleep(1)
        shuffled = random.sample(MOCK_TITLES, min(len(MOCK_TITLES), 8))
        return {"success": True, "titles": shuffled, "source": "mock"}
    
    # Real OpenAI API call
    try:
        system_prompt = config.get("prompts", {}).get("title_generation", "영미권 콘텐츠 마케팅 전문가입니다. 스토리 분석 후 영어 제목 8개를 JSON 배열로 반환하세요.")
        
        response = client.responses.create(
            model="gpt-5.2",
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"다음 스토리에 어울리는 영어 제목을 제안해주세요:\n\n{req.storyPreview}"}
            ]
        )
        
        output_text = response.output_text
        
        json_match = re.search(r'\[.*\]', output_text, re.DOTALL)
        if json_match:
            titles = json.loads(json_match.group())
        else:
            # Fallback: extract titles from text
            lines = [line.strip() for line in output_text.split('\n') if line.strip()]
            titles = [{"title": line[:50], "style": "general"} for line in lines[:8]]
        
        return {"success": True, "titles": titles, "source": "openai"}
    except Exception as e:
        print(f"OpenAI Titles Error: {e}")
        shuffled = random.sample(MOCK_TITLES, min(len(MOCK_TITLES), 8))
        return {"success": True, "titles": shuffled, "source": "mock_fallback", "error": str(e)}

# ==========================================
# [Core Logic] Parameter Calculator
# ==========================================
def calculate_parameters(mode: str, concept: str, cuts: int, selected_title: str = ""):
    params = {
        "resolution_w": 1920 if mode == "Long Form (16:9)" else 1080,
        "resolution_h": 1080 if mode == "Long Form (16:9)" else 1920,
        "mode_name": "LONG_FORM" if mode == "Long Form (16:9)" else "SHORT_FORM",
        "total_cuts": cuts,
        "concept": concept,
        "image_filename": "korean_woman_wide.png" if mode == "Long Form (16:9)" else "korean_woman_tall.png",
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
        params["cut_instruction"] = f"{cuts}컷의 기본 워크플로우 생성"

    return params

# ==========================================
# [API] History
# ==========================================
@app.get("/api/history")
async def get_history():
    history = []
    if not os.path.exists(OUTPUTS_DIR):
        return []
    
    folders = sorted(os.listdir(OUTPUTS_DIR), reverse=True)
    for folder_name in folders:
        folder_path = os.path.join(OUTPUTS_DIR, folder_name)
        if os.path.isdir(folder_path):
            images = sorted([f for f in os.listdir(folder_path) if f.endswith(('.png', '.jpg'))])
            meta_path = os.path.join(folder_path, "metadata.json")
            
            title = folder_name
            mode = "Unknown"
            timestamp = folder_name.split('_')[0] if '_' in folder_name else ""
            stats = {"cuts": 0}
            
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, 'r') as f:
                        meta = json.load(f)
                        title = meta.get("title", title)
                        mode = meta.get("mode", mode)
                        stats["cuts"] = meta.get("cuts", len(images))
                except:
                    pass
            
            thumbnails = [f"/outputs/{folder_name}/{img}" for img in images[:3]]
            
            history.append({
                "id": folder_name,
                "title": title,
                "mode": mode,
                "timestamp": timestamp,
                "thumbnails": thumbnails,
                "folder_name": folder_name,
                "image_count": stats["cuts"]
            })
    return history

@app.get("/api/history/{folder_name}")
async def get_project_details(folder_name: str):
    folder_path = os.path.join(OUTPUTS_DIR, folder_name)
    if not os.path.exists(folder_path):
        return {"error": "Not found"}
    
    images = sorted([f for f in os.listdir(folder_path) if f.endswith(('.png', '.jpg'))])
    meta_path = os.path.join(folder_path, "metadata.json")
    meta = {}
    if os.path.exists(meta_path):
        with open(meta_path, 'r') as f:
            meta = json.load(f)
            
    return {
        "title": meta.get("title", folder_name),
        "assets": [f"/outputs/{folder_name}/{img}" for img in images],
        "metadata": meta
    }

@app.delete("/api/history/{folder_name}")
async def delete_history(folder_name: str):
    folder_path = os.path.join(OUTPUTS_DIR, folder_name)
    if os.path.exists(folder_path) and os.path.isdir(folder_path):
        abs_outputs = os.path.abspath(OUTPUTS_DIR)
        abs_target = os.path.abspath(folder_path)
        if not abs_target.startswith(abs_outputs):
            return {"success": False, "error": "Invalid path"}
        shutil.rmtree(folder_path)
        return {"success": True}
    return {"success": False, "error": "Folder not found"}

# ==========================================
# [Mock Generator] SSE Stream
# ==========================================
async def mock_comfyui_process_generator(params: dict, topic: str) -> AsyncGenerator[str, None]:
    def create_sse_event(data: dict):
        return f"data: {json.dumps(data)}\n\n"

    def get_time():
        return time.strftime("%H:%M:%S")

    yield create_sse_event({"type": "log", "message": f"[{get_time()}] 🚀 워크플로우 초기화 (컨셉: {params['concept']})..."})
    await asyncio.sleep(0.5)

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    title_to_use = params.get("selected_title", topic[:20]) if params.get("selected_title") else (topic[:20] if topic else "Untitled_Project")
    folder_name = f"{timestamp}_{title_to_use.replace(' ', '_').replace(':', '')}"
    project_dir = os.path.join(OUTPUTS_DIR, folder_name)
    os.makedirs(project_dir, exist_ok=True)

    total_cuts = params['total_cuts']
    yield create_sse_event({"type": "log", "message": f"[{get_time()}] 📐 [Step 2] {total_cuts}컷 매핑 및 파라미터 최적화 완료."})
    
    src_img = os.path.join(ASSETS_DIR, params['image_filename'])
    
    for i in range(1, total_cuts + 1):
        if i % 10 == 0 or i == 1 or i == total_cuts:
            yield create_sse_event({"type": "log", "message": f"[{get_time()}] 🎨 [Asset Gen] Cut #{i}/{total_cuts} 생성 중..."})
            await asyncio.sleep(0.1)
        
        dest_filename = f"cut_{i:03d}.png"
        if os.path.exists(src_img):
            shutil.copy(src_img, os.path.join(project_dir, dest_filename))

    result_data = {
        "image_url": f"http://localhost:3501/outputs/{folder_name}/cut_001.png",
        "title": title_to_use,
        "mode": params["mode_name"],
        "cuts": total_cuts,
        "concept": params["concept"],
        "resolution": f"{params['resolution_w']}x{params['resolution_h']}"
    }
    
    with open(os.path.join(project_dir, "metadata.json"), 'w') as f:
        json.dump(result_data, f)

    yield create_sse_event({"type": "log", "message": f"[{get_time()}] ✅ [완료] {total_cuts}개 이미지 파일이 '{folder_name}' 경로에 저장되었습니다."})
    yield create_sse_event({"type": "result", "data": result_data})
    yield create_sse_event({"type": "done"})

@app.get("/api/stream")
async def stream_workflow(mode: str, topic: str, cuts: int = 20, concept: str = "기본 (Default)", title: str = ""):
    params = calculate_parameters(mode, concept, cuts, title)
    return StreamingResponse(
        mock_comfyui_process_generator(params, topic), 
        media_type="text/event-stream"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3501)
