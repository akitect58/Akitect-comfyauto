import time
import asyncio
import os
import json
import shutil
import random
import re
import sys
from typing import AsyncGenerator, List, Dict
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
import base64

# Ensure backend directory is in sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# ComfyUI client
from comfyui_client import ComfyUIClient
COMFYUI_AVAILABLE = True

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

# Default prompt templates with template variables: {{count}}, {{category}}, {{cut_number}}, {{character_tag}}, {{emotion_level}}, {{previous_summary}}, {{protagonist}}
DEFAULT_PROMPTS = {
    "protagonist_prompt": '''A majestic wild animal (specific species determined by story), detailed fur/skin texture, bright expressive eyes, natural lighting, photorealistic, 8k uhd, national geographic style''',
    
    "style_animation": '''A vertical 16:9 semi-realistic digital portrait styled as a classic Korean folk tale illustration. It depicts {{subject_description}}. The background is a dreamy, misty landscape of rolling hills, ancient trees, and blooming wild plants, rendered with soft brushstrokes and a warm, golden-hour light that creates a gentle glow and a sense of mystery. The overall feel is calm, traditional, and mythical, with a textured, aged paper effect. --ar 9:16''',

    "negative_prompt_photoreal": '''human, person, man, woman, child, clothes, clothing, dress, shirt, pants, 
anthropomorphic, standing on two legs, human hands, human face, talking animal, 
cgi, 3d render, cartoon, anime, illustration, painting, drawing, art, 
digital art, concept art, artstation, 
vibrant colors, oversaturated, neon, glowing, 
make-up, accessories, collar, leash, pet, domestic (unless specified), 
unrealistic proportions, mutant, extra limbs, 
blurry, low quality, low resolution, pixelated, 
watermark, signature, text, logo, banner, 
collage, multiple frames, split screen, border, 
smooth skin, plastic texture, wax figure''',

    "negative_prompt_animation": '''modern clothing, western features, exaggerated cartoon style, sharp photorealism, harsh lighting, overly saturated colors, text, watermarks, 
grayscale, black and white, horror, grotesque, deformed, bad anatomy, low quality, pixelated, blurry''',

    "script_parsing": '''You are a professional script breakdown assistant.
Analyze the provided screenplay/script text and convert it into a structured shot list (cuts).

[INPUT SCRIPT]
{{script}}

[REQUIREMENTS]
1. Parse every distinct scene or action into a cut.
2. If the user provided numbered list (e.g. "1. Scene..."), respect it.
3. If not numbered, break down by paragraphs or distinct actions.
4. Total cuts should match the content length.
5. Extract a consistent Character Tag if a main character is present.
6. Translate Korean descriptions to English descriptions if needed for 'physicsDetail' or 'sfxGuide' but keep 'description' in Korean.

[OUTPUT FORMAT]
return JSON object:
{
  "cuts": [
    {
      "cutNumber": 1,
      "description": "Scene description in Korean",
      "characterTag": "Identified main character or 'General'",
      "emotionLevel": 5,
      "cameraAngle": "eye_level",
      "lightingCondition": "natural_daylight",
      "weatherAtmosphere": "clear",
      "physicsDetail": "Action description in English",
      "sfxGuide": "Sound notes",
      "transitionHint": "cut"
    }
  ],
  "characterPrompt": "Detailed description of the main character extracted from text"
}''',

    "formatted_draft_generation": '''You are a professional video storyteller specializing in high-stakes nature documentaries and realistic animal dramas.
[INPUT]
Category: {{category}} (Select one if not specified: 1.Accident/Injury 2.Natural Disaster 3.Abuse/Neglect 4.Heroic Act 5.Urban Isolation 6.Abandonment 7.Maternal Love 8.Disability/Old Age 9.Interspecies Friendship 10.Companion to Socially Isolated)
Protagonist: {{protagonist}}

[TASK]
Generate 10 distinct story drafts. Each must be a 'Live-Action Only' realistic scenario.

[OUTPUT FORMAT]
JSON array of objects:
{
  "id": 1,
  "title": "Korean Title",
  "summary": "Korean Summary (~500 chars, inclusive of Introduction, Development, Turn, Conclusion)",
  "theme": "Survival/Bonding/etc",
  "atmosphere": "Detailed description of the mood (e.g., 'Rain-soaked grey city, cold metallic feel, muddy water rising')",
  "emotionalArc": "Despair -> Hope",
  "visualStyle": "Handheld camera, Natural lighting, High ISO grain"
}
Ensure title and summary land the emotional impact of the chosen category.''',

    "draft_generation": '''You are a professional video storyteller specializing in high-stakes nature documentaries and realistic animal dramas.

[INPUT]
Category: {{category}}
Protagonist: {{protagonist}}

[CATEGORY DEFINITIONS - CRITICAL]
1. 사고·부상 (Accident/Injury): 로드킬, 추락, 덫, 질병 등 직접적인 신체 위기.
2. 자연재해 (Natural Disaster): 홍수, 산불, 폭설, 지진 등 환경적 재앙 속 고립.
3. 학대·방치·호딩 (Abuse/Neglect): 짧은 목줄, 철장, 의도적인 가해 및 방치 상황.
4. 보은 및 영웅적 행동 (Heroic Act): 화재 알림, 아이 구조 등 동물의 충성심과 경이로움.
5. 도시형 고립 (Urban Isolation): 맨홀 추락, 벽 사이 고립 등 인간 구조물에 갇힌 상황.
6. 유기 및 유실 (Abandonment): 이사 시 버려짐, 휴게소 유기, 주인을 기다리다 지친 상황.
7. 모성애 (Maternal Love): 새끼를 살리기 위해 위험을 무릅쓰는 어미 동물의 사투.
8. 장애 및 노령 동물의 생존 (Disability/Old Age): 신체 불편함이나 노령으로 길 위에서 버티는 삶.
9. 종을 뛰어넘는 우정 (Interspecies Friendship): 서로 다른 종끼리 돕고 의지하는 경이로운 상황.
10. 사회적 약자와의 동행 (Companion): 노숙자, 독거노인 등의 유일한 친구로서의 유대와 고난.

[TASK]
Generate {{count}} distinct story drafts based on the selected category logic.

[OUTPUT FORMAT]
JSON array of objects:
{
  "id": 1,
  "title": "Korean Title",
  "summary": "Korean Summary (~500 chars)",
  "theme": "Specific sub-theme",
  "atmosphere": "Detailed mood",
  "emotionalArc": "Despair -> Hope",
  "visualStyle": "Handheld, Natural lighting"
}''',

    "story_confirmation": '''You are a professional video production screenwriter specialized in high-impact narrative storytelling.

[TASK]
Expand the selected story draft into exactly {{cut_count}} detailed cuts for video production.

[STORY CONTEXT]
Title: {{story_title}}
Summary: {{story_summary}}
Atmosphere: {{atmosphere}}
Character Tag: {{character_tag}}

[CORE RULES]
1. MASTER CHARACTER TAG: Every cut MUST start with "{{character_tag}}" in the characterTag field.
2. PHYSICS LOGIC: Specify physical interactions (Pressing, Grasping, Stepping) with surface details.
3. TIMING CONTROL: Describe the 'MOMENT BEFORE' the action (e.g., 'poised to jump', 'about to bark'). NEVER describe the action in mid-air/mid-motion.
4. CHAIN PROMPTING: Review previous cuts to ensure continuity.

[CUT STRUCTURE - Each cut requires:]
- cutNumber: Sequential number (1-{{cut_count}})
- description: Scene summary in Korean.
- imagePrompt: **CRITICAL** Detailed ENGLISH prompt for Stable Diffusion. MUST follow this format:
  "[Master Character Description], [Action/Pose: poised to..., preparing to...], [Environment], [Lighting: Natural/Dramatic], [Camera: 35mm/85mm, Angle], [Atmosphere: Rain/Dust/Fog], [Tech: 8k uhd, photorealistic, raw footage]"
- characterTag: "{{character_tag}}"
- emotionLevel: 1-10 scale
- cameraAngle: ground_level (for animals) | eye_level | high_angle | drone_shot
- lightingCondition: natural_daylight | golden_hour | overcast | night | dramatic_shadows
- physicsDetail: Specific interaction (e.g., "Paws pressing into soft mud", "Claws gripping the rusty metal")
- sfxGuide: Sound notes (Distance: Near/Far, e.g., "Muffled rain sound", "Crisp twig snap")
- transitionHint: cut | dissolve | fade

[PACING GUIDE]
- Cuts 1-5: HOOK - Most dramatic/tense moment (start in media res)
- Cuts 6-20: SETUP - Establish situation, build empathy
- Cuts 21-60: DEVELOPMENT - Rising tension, obstacles, attempts
- Cuts 61-85: CLIMAX - Peak crisis and turning point
- Cuts 86-{{cut_count}}: RESOLUTION - Final outcome, victory, or emotional payoff

[OUTPUT FORMAT]
{
  "cuts": [...],
  "characterPrompt": "Detailed master character description for image generation",
  "storyArc": {
    "hook": "Brief description of hook moment",
    "climax": "Brief description of climax",
    "resolution": "Brief description of resolution"
  }
}''',

    "story_chunk_generation": '''You are generating a specific chunk of a 100-cut video screenplay. 

[CONTEXT]
Title: {{story_title}}
Current Chunk: Cuts {{start_cut}} to {{end_cut}}
Previous Context: {{previous_context}}
Atmosphere: {{atmosphere}}
Character Tag: The Wild Animal

[REQUIREMENTS]
- Generate exactly {{chunk_size}} cuts.
- Maintain perfect continuity with Previous Context.
- **Start with cut number {{start_cut}}**.
- **FIELDS (MANDATORY)**:
  1. cutNumber (int)
  2. description (String, **KOREAN**): Visual scene summary.
  3. imagePrompt (String, **ENGLISH**): Detailed SDXL prompt.
  4. characterTag (String): 'The Wild Animal'
  5. physicsDetail (String)
  6. sfxGuide (String)

[OUTPUT EXAMPLE]
{
  "cuts": [
    {
      "cutNumber": 1,
      "description": "한글 설명...",
      "imagePrompt": "English prompt...",
      "characterTag": "The Wild Animal",
      "physicsDetail": "...",
      "sfxGuide": "..."
    }
  ]
}''',

    "single_cut_regeneration": '''You are regenerating a single cut within an existing story sequence.

[CONTEXT]
Story Title: {{story_title}}
Character Tag: {{character_tag}}
Cut Number: {{cut_number}} of {{total_cuts}}
Previous Cut Summary: {{previous_cut}}
Next Cut Summary: {{next_cut}}
Current Emotion Level Range: {{emotion_range}}

[REQUIREMENTS]
- Maintain narrative continuity with surrounding cuts
- Keep character tag exactly as: {{character_tag}}
- Emotion level should fit the story arc position
- Physical actions must connect logically to previous/next cuts

[OUTPUT]
Generate a single cut object with all required fields maintaining story coherence.''',

    "master_character": '''You are a photorealistic image prompt specialist.

[TASK]
Create a single 'Master Character Prompt' that defines the protagonist's specialized visual DNA.

[INPUT]
Character Info: {{character_description}}

[FOCUS]
1. SPECIES/BREED: Exact definition.
2. TEXTURE: Fur/Skin details (matted, wet, scarred, fluffy).
3. MARKINGS: Unique visual identifiers (torn ear, specific patch).
4. ITEMS: Collar (color/texture), harness (if applicable).

[RESTRICTIONS]
- NO background.
- NO action.
- NO lighting.

[OUTPUT]
Single paragraph, English only. Comma-separated descriptors. Optimized for SDXL/RealVisXL.''',

    "veo_video": '''You are a Veo 3.1 Prompt Specialist. Convert the scene data into the strict 5-Element Formula.

[INPUT]
Description: {{scene_description}}
Physics: {{physics_detail}}
SFX: {{sfx_guide}}
Emotion: {{emotion_level}}

[5-ELEMENT FORMULA]
1. CINEMATOGRAPHY: 
   - Emot 1-4: 35mm Wide
   - Emot 5-7: 50mm Medium
   - Emot 8-10: 85mm+ Close-up
   - Angle: Ground-level (for animal)
   - Move: Static/Pan/Handheld (based on tension)
2. SUBJECT: "{{character_tag}}" (Do not re-describe appearance, assume IP-Adapter handles it). State POSTURE/STATE only.
3. ACTION: Present continuous. Use physics verbs (Pressing against, Stepping on).
4. CONTEXT: Location, Weather, 'Dirty Frame' elements (rain, dust between lens and subject).
5. STYLE & AMBIANCE: Natural lighting, Raw footage, High ISO grain. [SFX: {{sfx_guide}}]

[OUTPUT]
One paragraph. English. NO intro/outro.''',

    "scene_image": '''You are converting cinematic scene descriptions into SDXL/FLUX image generation prompts.

[SCENE INPUT]
Cut Number: {{cut_number}}
Description: {{scene_description}}
Character Tag: {{character_tag}}
Emotion Level: {{emotion_level}}/10
Camera: {{camera_angle}}
Lighting: {{lighting_condition}}
Weather: {{weather_atmosphere}}

[TIMING CONTROL - CRITICAL]
Generate the MOMENT BEFORE action, not during:
(X) BAD: "dog is jumping", "running across", "falling down"
(OK) GOOD: "poised to jump, muscles tensed", "about to sprint, weight shifted forward", "on the verge of falling, balance lost"

Keywords: "about to [verb]", "preparing to [verb]", "on the verge of [verb]", "poised for [action]"

[COMPOSITION RULES]
- Emotion 1-4: Wide establishing shots, environmental context
- Emotion 5-7: Medium shots, subject-environment balance
- Emotion 8-10: Tight close-ups, facial details, emotional impact

[ATMOSPHERE ELEMENTS]
Include between subject and camera when relevant:
- Rain: water droplets on lens, wet surfaces
- Fire: ash particles, heat distortion, smoke wisps
- Dust: floating particles, hazy air
- Snow: falling flakes, frost on surfaces

[REQUIRED TECHNICAL KEYWORDS]
natural lighting, raw footage aesthetic, high ISO grain, shot on 35mm lens, shallow depth of field, photojournalistic style

[CHARACTER REFERENCE]
Use "the [animal type]" or "the character" - actual appearance comes from master character prompt via IP-Adapter

[OUTPUT]
Single paragraph English prompt, no line breaks, optimized for photorealistic generation.''',

    "veo_video": '''You are a VEO 3.1 video prompt specialist.
    
[INPUT DATA]
Cut: {{cut_number}}
Description: {{scene_description}}
Character: {{character_tag}}
Emotion: {{emotion_level}}/10
Physics: {{physics_detail}}
SFX: {{sfx_guide}}

[STRUCTURE - 5-ELEMENT FORMULA (STRICT ORDER)]
1. Cinematography: Lens, Angle, Movement
2. Subject: Visuals, Costume, Texture
3. Action: Specific movement (Present Continuous)
4. Context: Location, Time, Weather, Atmosphere (Dirty Frame)
5. Style & Ambiance: Lighting, Color, SFX (No BGM/Dialogue)

[CINEMATIC LOGIC - AI MUST ADAPT]
- **Lens Control**:
  - Emotion 1-4: 35mm Wide (Context/Calm)
  - Emotion 5-7: 50mm Medium (Story/Focus)
  - Emotion 8-10: 85mm+ Close-up (Intense/Crisis) (Highlight contact points 50%+)
- **Camera Movement**:
  - Static/Pan (Calm) -> Handheld/Tracking (Tension/Chase) -> Drone/High Angle (Isolation/Intro)
- **Height**:
  - Animal: Ground-level (Eye-to-eye)
  - Human: Eye-level
- **Atmosphere (Dirty Frame)**:
  - If Rain/Fire/Dust: Describe particles (Ash, Raindrops, Smoke) between lens and subject.
  - Short focus distance for immersive depth.

[AUDIO RULES]
- **SFX ONLY**: Footsteps, Rain, Roar, Rustle.
- **FORBIDDEN**: "ominous music", "voiceover", "dialogue".

[OUTPUT FORMAT]
Single paragraph English prompt. End with [SFX: ...]. NO intro/outro.''',

    "title_generation": '''You are a viral content marketing specialist for Korean audiences.

[STORY CONTEXT]
Title: {{story_title}}
Summary: {{story_summary}}
Emotional Arc: {{emotional_arc}}

[GENERATE {{count}} TITLE OPTIONS]

[STYLE CATEGORIES]
- impact: Action-oriented, dramatic tension, urgency
- emotional: Heartwarming, tear-jerker, redemption arc
- documentary: Factual, observational, authentic feel
- mystery: Curiosity-driven, question-based, reveal-focused

[TITLE FORMULAS TO USE]
1. Tension + Time: "48시간: 마지막 승부"
2. Location + Crisis: "심연 속으로: 기적의 탈출"
3. Personal Stake: "모든 것을 바꾼 비밀"
4. High Pursuit: "불타는 대지 위에서"
5. Triumph: "그럼에도 불구하고: 어둠 속의 빛"

[REQUIREMENTS]
- **LANGUAGE: KOREAN (Must be in Korean)**
- Maximum 8 words per title
- Must work as YouTube/social video title
- Include emotional hook
- Avoid clichés like "Amazing", "Unbelievable"

[OUTPUT FORMAT]
JSON array: [{"title": "Korean Title", "style": "category", "hook": "Why this works"}]''',

    "negative_prompt": "" 
}


# Config helpers
def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r', encoding='utf-8-sig') as f:
            config = json.load(f)
            # 기본 프롬프트 병합 (사용자 설정이 없으면 기본값 사용)
            if "prompts" not in config:
                config["prompts"] = {}
            for key, value in DEFAULT_PROMPTS.items():
                # Migration: if the prompt is missing, empty, or contains the old animal rescue persona, update to new default
                current_val = config["prompts"].get(key, "")
                if not current_val or "animal rescue" in current_val.lower() or "A Dog's Fight for Survival" in current_val:
                    config["prompts"][key] = value
            return config
    return {"openai_api_key": "", "comfyui_path": "", "prompts": DEFAULT_PROMPTS.copy()}

def save_config(config):
    with open(CONFIG_PATH, 'w', encoding='utf-8-sig') as f:
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
# [API] Settings
# ==========================================

class SettingsUpdate(BaseModel):
    openai_api_key: str | None = None
    comfyui_path: str | None = None
    use_reference_image: bool | None = None
    prompts: dict | None = None

@app.get("/api/settings")
async def get_settings():
    """Get current settings (API key masked)"""
    try:
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
            "use_reference_image": config.get("use_reference_image", True),
            "prompts": config.get("prompts", {})
        }
    except Exception as e:
        print(f"Error loading settings: {e}")
        return {
            "openai_api_key_masked": "",
            "openai_api_key_set": False,
            "comfyui_path": "",
            "use_reference_image": True,
            "prompts": {},
            "error": str(e)
        }

@app.put("/api/settings")
async def update_settings(settings: SettingsUpdate):
    """Update settings"""
    config = load_config()
    
    if settings.openai_api_key is not None:
        config["openai_api_key"] = settings.openai_api_key
    if settings.comfyui_path is not None:
        config["comfyui_path"] = settings.comfyui_path
    if settings.use_reference_image is not None:
        config["use_reference_image"] = settings.use_reference_image
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

class RegenerateDraftRequest(BaseModel):
    draftId: int
    mode: str = "long"
    category: str | None = None
    customInput: str | None = None

class StoryRequest(BaseModel):
    mode: str
    draftId: int
    draftTitle: str
    draftSummary: str

class RegenerateCutRequest(BaseModel):
    cutNumber: int
    totalCuts: int
    storyTitle: str
    characterTag: str
    previousCut: dict | None = None
    nextCut: dict | None = None
    emotionRange: str = "5-7"

class UploadRequest(BaseModel):
    image: str # Base64 string
    filename: str


class TitleRequest(BaseModel):
    storyPreview: str

class ParseScriptRequest(BaseModel):
    script: str
    mode: str = "long"

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
        
        # Replace template variables
        system_prompt = system_prompt.replace("{{count}}", "10")
        system_prompt = system_prompt.replace("{{category}}", req.category or "ALL")
        
        # Force Korean response
        system_prompt += "\n\n[중요] 모든 응답은 반드시 한국어로 작성하세요. title과 summary 모두 한국어로 작성하세요."
        
        user_input = req.customInput if req.customInput else f"카테고리: {req.category}"
        
        response = client.responses.create(
            model="gpt-5-mini-2025-08-07",
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

# Streaming version of drafts API
from sse_starlette.sse import EventSourceResponse

@app.get("/api/workflow/drafts/stream")
async def generate_drafts_stream(mode: str = "long", category: str = None, customInput: str = None):
    """Streaming version: Generate 10 story drafts with live text output"""
    config = load_config()
    client = get_openai_client()
    
    async def event_generator():
        # If no API key, use mock streaming
        if not client:
            mock_text = "AI가 스토리 초안을 생성하고 있습니다...\n\n"
            for char in mock_text:
                yield {"event": "delta", "data": json.dumps({"text": char})}
                await asyncio.sleep(0.02)
            
            drafts = [
                {"id": i+1, "title": f"Mock Story {i+1}", "summary": f"이것은 Mock 데이터입니다. API 키를 설정하면 실제 AI가 생성합니다.", "theme": "mock"}
                for i in range(10)
            ]
            yield {"event": "complete", "data": json.dumps({"drafts": drafts, "source": "mock"})}
            return
        
        try:
            system_prompt = config.get("prompts", {}).get("draft_generation", "당신은 실사 영상 스토리 작가입니다. 10가지 스토리 초안을 JSON 배열로 반환하세요.")
            protagonist_prompt = config.get("prompts", {}).get("protagonist_prompt", "20대 중반의 한국인 여성")
            
            system_prompt = system_prompt.replace("{{count}}", "10")
            system_prompt = system_prompt.replace("{{category}}", category or "ALL")
            system_prompt = system_prompt.replace("{{protagonist}}", protagonist_prompt)
            system_prompt += "\n\n[중요] 모든 응답은 반드시 한국어로 작성하세요. title과 summary 모두 한국어로 작성하세요."
            
            user_input = customInput if customInput else f"카테고리: {category}"
            
            # Streaming API call
            stream = client.responses.create(
                model="gpt-5-mini-2025-08-07",
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input}
                ],
                stream=True
            )
            
            full_text = ""
            for event in stream:
                if hasattr(event, 'type'):
                    if event.type == 'response.output_text.delta':
                        delta_text = event.delta
                        full_text += delta_text
                        yield {"event": "delta", "data": json.dumps({"text": delta_text})}
                    elif event.type == 'response.completed':
                        # Parse final JSON
                        json_match = re.search(r'\[.*\]', full_text, re.DOTALL)
                        if json_match:
                            drafts = json.loads(json_match.group())
                        else:
                            drafts = [{"id": 1, "title": "Parse Error", "summary": full_text[:500], "theme": "error"}]
                        yield {"event": "complete", "data": json.dumps({"drafts": drafts, "source": "openai"})}
                        
        except Exception as e:
            yield {"event": "error", "data": json.dumps({"error": str(e)})}
    
    return EventSourceResponse(event_generator())


@app.post("/api/workflow/draft/regenerate")
async def regenerate_draft(req: RegenerateDraftRequest):
    """Regenerate a single draft"""
    config = load_config()
    client = get_openai_client()
    
    if not client:
        # Mock fallback
        time.sleep(1)
        return {
            "success": True, 
            "draft": {
                "id": req.draftId, 
                "title": f"Regenerated Mock {req.draftId}", 
                "summary": "This is a regenerated mock draft due to missing API key.", 
                "theme": "mock"
            }
        }

    try:
        protagonist_prompt = config.get("prompts", {}).get("protagonist_prompt", "20대 중반의 한국인 여성")
        base_prompt = config.get("prompts", {}).get("draft_generation", "스토리 작가입니다.")
        base_prompt = base_prompt.replace("{{protagonist}}", protagonist_prompt)
        base_prompt = base_prompt.replace("{{category}}", req.category or "ALL")

        user_input = req.customInput if req.customInput else f"카테고리: {req.category}"

        single_prompt = base_prompt.replace("{{count}}", "1")
        single_prompt += f"\n\n지금 생성할 초안 번호: {req.draftId}/10"
        single_prompt += "\n반드시 단일 객체만 반환: {\"id\": " + str(req.draftId) + ", \"title\": \"...\", \"summary\": \"...\", \"theme\": \"...\"}"
        single_prompt += "\n[중요] summary와 title 모두 한국어로 작성하세요."

        response = client.responses.create(
            model="gpt-5-mini-2025-08-07",
            input=[
                {"role": "system", "content": single_prompt},
                {"role": "user", "content": user_input}
            ]
        )
        
        output_text = response.output_text
        json_match = re.search(r'\{.*\}', output_text, re.DOTALL)
        
        if json_match:
            draft = json.loads(json_match.group())
            draft["id"] = req.draftId
        else:
            draft = {"id": req.draftId, "title": "Regeneration Error", "summary": output_text[:500], "theme": "error"}
            
        return {"success": True, "draft": draft}

    except Exception as e:
        return {"success": False, "error": str(e), "draft": {"id": req.draftId, "title": "API Error", "summary": str(e), "theme": "error"}}


# Parallel version - 10 API calls at once
@app.get("/api/workflow/drafts/parallel")
async def generate_drafts_parallel(mode: str = "long", category: str = None, customInput: str = None):
    """
    Serial version (formerly parallel): Generate 10 story drafts sequentially.
    Feeds previous summaries into the next prompt to ensure diversity.
    """
    config = load_config()
    client = get_openai_client()
    
    async def event_generator():
        if not client:
            # Mock serial simulation
            previous_mock_summaries = []
            for i in range(10):
                draft_id = i + 1
                mock_text = f"Mock 스토리 #{draft_id} 생성 중... (직렬 처리: 이전 {len(previous_mock_summaries)}개 참고)"
                
                # Simulate streaming
                for char in mock_text:
                    yield {"event": "delta", "data": json.dumps({"draft_id": draft_id, "text": char})}
                    await asyncio.sleep(0.02)
                
                # Draft Complete
                draft_data = {
                    "id": draft_id,
                    "title": f"Mock Story {draft_id}",
                    "summary": mock_text,
                    "theme": "mock"
                }
                yield {"event": "draft", "data": json.dumps(draft_data)}
                previous_mock_summaries.append(mock_text)
                
            yield {"event": "complete", "data": json.dumps({"total": 10, "source": "mock_serial"})}
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
                
                # Construct Prompt with Context
                current_prompt = base_prompt_template.replace("{{count}}", "1")
                current_prompt += f"\n\n지금 생성할 초안 번호: {draft_id}/10"
                
                if previous_summaries:
                    current_prompt += "\n\n[이전에 생성된 초안들 (중복 회피용)]"
                    for idx, summary in enumerate(previous_summaries):
                        # Limit summary length to save tokens if needed, though summaries are usually short
                        current_prompt += f"\n- {idx+1}. {summary[:100]}..."
                    current_prompt += "\n\n[지시사항] 위 안들과는 소재, 전개, 분위기가 **완전히 다른** 새로운 이야기를 만드세요. 겹치는 설정이 없도록 하세요."
                
                current_prompt += "\n반드시 단일 객체만 반환: {\"id\": " + str(draft_id) + ", \"title\": \"...\", \"summary\": \"...\", \"theme\": \"...\"}"
                current_prompt += "\n[중요] summary와 title 모두 한국어로 작성하세요."

                try:
                    # Async stream request
                    stream = client.chat.completions.create(
                        model="gpt-4o-mini", # Use a fast model
                        messages=[
                            {"role": "system", "content": current_prompt},
                            {"role": "user", "content": user_input}
                        ],
                        stream=True
                    )

                    full_response = ""
                    
                    # Process stream
                    for chunk in stream:
                        if chunk.choices[0].delta.content:
                            content = chunk.choices[0].delta.content
                            full_response += content
                            # Yield delta for UI
                            yield {"event": "delta", "data": json.dumps({"draft_id": draft_id, "text": content})}
                            # Small delay not needed for real API, but good for throttling if needed
                            # await asyncio.sleep(0.001) 

                    # Parse JSON
                    json_match = re.search(r'\{.*\}', full_response, re.DOTALL)
                    if json_match:
                        draft = json.loads(json_match.group())
                        draft["id"] = draft_id
                    else:
                        draft = {"id": draft_id, "title": f"Story #{draft_id}", "summary": full_response[:400], "theme": "parsed"}
                    
                    yield {"event": "draft", "data": json.dumps(draft)}
                    
                    # Add to context for next iteration
                    # Use title + summary for better context, or just summary
                    previous_summaries.append(f"[{draft.get('title', 'Untitled')}] {draft.get('summary', '')}")

                except Exception as e:
                    print(f"Error generating draft {draft_id}: {e}")
                    error_draft = {"id": draft_id, "title": f"Error #{draft_id}", "summary": str(e), "theme": "error"}
                    yield {"event": "draft", "data": json.dumps(error_draft)}
                    # Still append to keep index sync, or skip
                    previous_summaries.append("Error during generation")

            yield {"event": "complete", "data": json.dumps({"total": 10, "source": "openai_serial_context"})}

        except Exception as e:
            yield {"event": "error", "data": json.dumps({"error": str(e)})}
    
    return EventSourceResponse(event_generator())


# Reference image generation for protagonist consistency

class ReferenceImageRequest(BaseModel):
    mode: str
    style: str = "photoreal"
    cut: dict
    characterPrompt: str

@app.get("/api/settings/models")
async def get_available_models():
    """Fetch available checkpoint models from ComfyUI or local scan"""
    config = load_config()
    models = await fetch_available_models(config)
    return {"models": models}

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
    if comfy_path and os.path.exists(comfy_path):
        # Common paths: models/checkpoints, models/diffusion_models
        # User requested: models/diffusion_models specifically, but typically checkpoints are in models/checkpoints
        # We will scan both.
        models = []
        search_paths = [
            os.path.join(comfy_path, "models", "checkpoints"),
            os.path.join(comfy_path, "models", "diffusion_models")
        ]
        
        for p in search_paths:
            if os.path.exists(p):
                for root, dirs, files in os.walk(p):
                    for file in files:
                        if file.endswith((".safetensors", ".ckpt")):
                            # Rel path from the search path? ComfyUI usually expects filename relative to 'checkpoints' root or just filename
                            # If scanning diffusion_models, we might need full path or relative to that.
                            # For simplicity, we just return filename if flat, or relpath.
                            try:
                                rel = os.path.relpath(os.path.join(root, file), p)
                                models.append(rel)
                            except:
                                models.append(file)
        
        # Dedup and sort
        return sorted(list(set(models)))

    return []

# ==========================================
# [Helper] ComfyUI Workflow
# ==========================================

def load_workflow_template(workflow_name: str) -> dict:
    """Load a ComfyUI workflow template from the workflows directory"""
    workflow_path = os.path.join(BASE_DIR, "workflows", f"{workflow_name}.json")
    if os.path.exists(workflow_path):
        with open(workflow_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def prepare_workflow(template: dict, replacements: dict) -> dict:
    """Replace placeholder strings in workflow JSON safely"""
    import copy
    workflow = copy.deepcopy(template)
    
    # 1. Direct replacements in nodes (Model, Seed, etc.)
    target_model = replacements.get("ckpt_name")
    target_seed = replacements.get("seed")
    target_cut_num = replacements.get("cut_number", 1)
    
    for node_id, node in workflow.items():
        inputs = node.get("inputs", {})
        
        # Replace Model
        if target_model and node.get("class_type") == "CheckpointLoaderSimple":
            inputs["ckpt_name"] = target_model
            
        # Replace Seed in KSampler or similar
        if target_seed is not None and "seed" in inputs:
            inputs["seed"] = target_seed
            
        # Replace placeholders in any string input
        for key, value in inputs.items():
            if isinstance(value, str):
                for rk, rv in replacements.items():
                    placeholder = f"{rk.upper()}_PLACEHOLDER"
                    if placeholder in value:
                        inputs[key] = value.replace(placeholder, str(rv))
                        
    return workflow

def clean_string(s: str) -> str:
    """Remove control characters and normalize whitespace"""
    if not s: return ""
    # Remove control characters 0-31 except \n \r \t (though we really want to clean those too for SD)
    # Actually for Stable Diffusion, it's better to just have space instead of newlines
    s = str(s).replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
    # Keep only printable characters
    return "".join(c for c in s if c.isprintable() or ord(c) > 127).strip()

# ==========================================
# [Endpoints] Generation & Interaction
# ==========================================
@app.post("/api/workflow/generate-reference")
async def generate_reference_image(req: ReferenceImageRequest):
    """Generate the first reference image for protagonist consistency using ComfyUI"""
    config = load_config()
    
    # Get prompts
    protagonist_prompt = config.get("prompts", {}).get("protagonist_prompt", "A majestic wild animal")
    
    # Select prompts based on style
    if req.style == "animation":
        # Animation Style
        base_prompt = config.get("prompts", {}).get("style_animation", "")
        negative_prompt = config.get("prompts", {}).get("negative_prompt_animation", "")
        
        # Construct subject description (Protagonist + Action)
        cut_desc = req.cut.get("description", "")
        subject_desc = f"{protagonist_prompt}, {cut_desc}"
        
        positive_prompt = base_prompt.replace("{{subject_description}}", subject_desc)
    else:
        # Photorealistic Style (Default)
        negative_prompt = config.get("prompts", {}).get("negative_prompt_photoreal", "")
        if not negative_prompt: # Fallback
             negative_prompt = config.get("prompts", {}).get("negative_prompt", "")
             
        cut_description = req.cut.get("description", "")
        positive_prompt = f"photorealistic, 8K UHD, {protagonist_prompt}, {cut_description}"
    
    # Try ComfyUI first
    comfyui_path = config.get("comfyui_path", "")
    comfyui_server = "127.0.0.1:8188"
    
    # 1. Connection Check
    if not check_comfyui_connection(host=comfyui_server.split(':')[0], port=int(comfyui_server.split(':')[1])):
         return {
            "success": False,
            "error": "❌ ComfyUI 서버(127.0.0.1:8188)가 켜져있지 않습니다. 실행 후 다시 시도해주세요."
        }

    try:
        # Load workflow template
        workflow_template = load_workflow_template("reference_generation")
        if not workflow_template:
            raise Exception("Workflow template not found")
        
        # Prepare workflow with actual values
        import random
        seed = random.randint(0, 2**32 - 1)
        
        # Get selected model
        selected_model = config.get("selected_model", "RealVisXL_V5.0.safetensors")
        
        # [Smart Fallback] Check if model exists, otherwise use first available
        available_models = await fetch_available_models(config)
        if available_models:
            if selected_model not in available_models:
                print(f"⚠️ Model '{selected_model}' not found, using '{available_models[0]}' instead.")
                selected_model = available_models[0]

        workflow = prepare_workflow(workflow_template, {
            "positive_prompt": positive_prompt,
            "negative_prompt": negative_prompt,
            "seed": seed,
            "cut_number": req.cut.get("cutNumber", 1),
            "ckpt_name": selected_model
        })
                                                                                                                                                                                                                                                                                    
        # Initialize ComfyUI client
        client = ComfyUIClient(comfyui_server)
        
        # Queue the prompt
        result = client.queue_prompt(workflow)
        prompt_id = result.get("prompt_id")
        
        if not prompt_id:
            raise Exception("Failed to queue prompt")
        
        # Wait for completion (with timeout)
        max_wait = 120  # seconds
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            history = client.get_history(prompt_id)
            if prompt_id in history:
                outputs = history[prompt_id].get("outputs", {})
                for node_id, node_output in outputs.items():
                    if "images" in node_output:
                        image_info = node_output["images"][0]
                        # Get the image
                        image_data = client.get_image(
                            image_info["filename"],
                            image_info.get("subfolder", ""),
                            image_info.get("type", "output")
                        )
                        
                        # Convert to base64 data URL
                        image_base64 = base64.b64encode(image_data).decode('utf-8')
                        image_url = f"data:image/png;base64,{image_base64}"
                        
                        # Save reference image path for later use
                        reference_path = os.path.join(OUTPUTS_DIR, f"reference_{prompt_id}.png")
                        with open(reference_path, 'wb') as f:
                            f.write(image_data)
                        
                        return {
                            "success": True,
                            "imageUrl": image_url,
                            "imagePath": reference_path,
                            "protagonistPrompt": protagonist_prompt,
                            "cutNumber": req.cut.get("cutNumber", 1),
                            "source": "comfyui",
                            "seed": seed
                        }
                break
            await asyncio.sleep(1)
        
        raise Exception("ComfyUI timeout")
        
    except Exception as e:
        print(f"ComfyUI error: {e}")
        return {
            "success": False,
            "error": str(e)
        }


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
            "새벽녘, 고요한 숲속. 이슬 맺힌 풀잎 사이로 한 마리의 야생 동물이 조심스레 발을 내딛는다.",
            "갑작스러운 인기척. 귀를 쫑긋 세우고 주변을 경계하는 모습.",
            "거친 숨소리와 함께 시작된 질주. 흙먼지가 피어오른다.",
            "천적을 피해 낡은 나무 둥치 아래로 몸을 숨긴다. 긴장된 눈빛.",
            "비가 그치고 드러난 무지개 아래, 다시 여정을 시작하는 뒷모습.",
        ]
        for i in range(1, total_cuts + 1):
            cuts.append({"cutNumber": i, "description": cut_descriptions[(i - 1) % len(cut_descriptions)] + f" (컷 {i})"})
        
        character_prompt = "[Mock] 메인 캐릭터 - 야생 동물(늑대/여우/사슴 등), 자연스러운 털 질감, 야생의 분위기"
        return {"success": True, "totalCuts": total_cuts, "cuts": cuts, "characterPrompt": character_prompt, "source": "mock"}
    
    # Real OpenAI API call
    try:
        system_prompt = config.get("prompts", {}).get("story_confirmation", "")
        
        # Always enforce imagePrompt requirement (override any config)
        image_prompt_instruction = (
            "\n\n[중요 추가 지침] 각 컷에는 반드시 'imagePrompt' 필드를 포함하세요. "
            "'imagePrompt'는 Stable Diffusion 이미지 생성용 **상세 영문 프롬프트**입니다. "
            "예: \"A lone wolf standing on a rocky outcrop, howling at the moon, mist swirling, photorealistic, 8K UHD\""
        )
        
        if not system_prompt:
            system_prompt = config.get("prompts", {}).get("story_confirmation", DEFAULT_PROMPTS.get("story_confirmation", ""))
        else:
            system_prompt = system_prompt.replace("{cuts}", str(total_cuts))
        
        # Always append the imagePrompt instruction
        system_prompt += image_prompt_instruction
        
        user_input = (
            f"제목: {req.draftTitle}\n\n초안 요약:\n{req.draftSummary}\n\n"
            f"위 초안을 바탕으로 {total_cuts}컷의 상세 스토리와 캐릭터 묘사를 생성해주세요.\n"
            f"필수: 각 컷에 'description'(한글)과 'imagePrompt'(영문)를 모두 포함하세요."
        )
        
        response = client.responses.create(
            model="gpt-5-mini-2025-08-07",
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
            character_prompt = parsed.get("characterPrompt", "A majestic wild animal (Fallback)")
        else:
            # Fallback: create simple cuts from text
            lines = output_text.split('\n')
            cuts = [{"cutNumber": i+1, "description": line[:200], "imagePrompt": f"Scene {i+1}, {req.draftTitle}"} for i, line in enumerate(lines[:total_cuts]) if line.strip()]
            character_prompt = "A majestic wild animal (Parsing Fallback)"
        
        return {"success": True, "totalCuts": total_cuts, "cuts": cuts, "characterPrompt": character_prompt, "source": "openai"}
    except Exception as e:
        print(f"OpenAI Story Error: {e}")
        cuts = [{"cutNumber": 1, "description": f"API 오류: {str(e)}"}]
        return {"success": True, "totalCuts": 1, "cuts": cuts, "characterPrompt": str(e), "source": "error"}



@app.post("/api/workflow/story/parse")
async def parse_script(req: ParseScriptRequest):
    """Parse raw script into cuts"""
    config = load_config()
    client = get_openai_client()
    
    # If no API key, use mock data
    if not client:
        await asyncio.sleep(1)
        lines = [l for l in req.script.split('\n') if l.strip()]
        cuts = []
        for i, line in enumerate(lines[:10]):
            cuts.append({
                "cutNumber": i+1,
                "description": line,
                "characterTag": "Protagonist",
                "emotionLevel": 5,
                "cameraAngle": "eye_level",
                "lightingCondition": "natural",
                "weatherAtmosphere": "clear",
                "physicsDetail": "Standing",
                "sfxGuide": "Silence",
                "transitionHint": "cut"
            })
        return {"success": True, "totalCuts": len(cuts), "cuts": cuts, "characterPrompt": "Mock Character", "source": "mock"}

    try:
        system_prompt = config.get("prompts", {}).get("script_parsing", "")
        if not system_prompt:
            system_prompt = config.get("prompts", {}).get("script_parsing", DEFAULT_PROMPTS.get("script_parsing", "Parse the script into JSON cuts."))
            
        system_prompt = system_prompt.replace("{{script}}", req.script)
        
        response = client.responses.create(
            model="gpt-5-mini-2025-08-07",
            input=[
                {"role": "system", "content": "You are a script parser JSON generator."},
                {"role": "user", "content": system_prompt}
            ]
        )
        
        output_text = response.output_text
        json_match = re.search(r'\{.*\}', output_text, re.DOTALL)
        
        if json_match:
            parsed = json.loads(json_match.group())
            return {"success": True, "totalCuts": len(parsed.get("cuts", [])), "cuts": parsed.get("cuts", []), "characterPrompt": parsed.get("characterPrompt", ""), "source": "openai"}
        else:
            return {"success": False, "error": "Parsing failed", "raw_output": output_text}
            
    except Exception as e:
        return {"success": False, "error": str(e)}

import uuid

# In-memory storage for story generation requests to avoid URL length limits
temp_story_data = {}

class PrepareStoryRequest(BaseModel):
    draftId: int
    draftTitle: str
    draftSummary: str
    mode: str

@app.post("/api/workflow/story/prepare")
async def prepare_story_generation(req: PrepareStoryRequest):
    request_id = str(uuid.uuid4())
    temp_story_data[request_id] = {
        "draftId": req.draftId,
        "draftTitle": req.draftTitle,
        "draftSummary": req.draftSummary,
        "mode": req.mode
    }
    return {"requestId": request_id}

@app.get("/api/workflow/story/stream")
async def story_generation_stream(
    requestId: str = None, 
    draftId: int = None, 
    draftTitle: str = None, 
    draftSummary: str = None, 
    mode: str = "long"
):
    """Step 2 (Streaming): Generate story with real-time text streaming using ID or direct params"""
    
    # 1. Try to load context from Request ID (preferred)
    if requestId:
        if requestId not in temp_story_data:
            async def error_generator():
                yield {"event": "error", "data": json.dumps({"error": "Expired or invalid request ID"})}
            return EventSourceResponse(error_generator())
        
        data = temp_story_data[requestId]
        draftTitle = data["draftTitle"]
        draftSummary = data["draftSummary"]
        mode = data["mode"]
    
    # 2. Fallback: Use direct parameters if Request ID is missing
    elif draftTitle and draftSummary:
        # Direct generation (fallback for legacy clients)
        pass 
    else:
        # Neither provided
        async def error_generator():
             yield {"event": "error", "data": json.dumps({"error": "Missing parameters (requestId or draft details)"})}
        return EventSourceResponse(error_generator())
        
    total_cuts = 100 if mode == "long" else 20
    
    config = load_config()
    client = get_openai_client()
    
    print(f"Starting story stream for draft: {draftTitle} ({mode})")

    async def event_generator():
        # Remove data after use (or keep it if retries needed? let's keep for now or TTL)
        # temp_story_data.pop(requestId, None) 
        
        if not client:
            print("Error: No OpenAI Client available")
            yield {"event": "error", "data": json.dumps({"error": "OpenAI API Key 설정이 필요합니다."})}
            return

        # Real OpenAI Streaming
        # Real OpenAI Streaming
        try:
            print("Starting Sequential Chain Prompting (10 cuts per chunk)...")
            
            chunk_size = 10
            previous_context_summary = f"Title: {draftTitle}\nSummary: {draftSummary}"
            generated_cuts = []
            
            for start_idx in range(0, total_cuts, chunk_size):
                end_idx = min(start_idx + chunk_size, total_cuts)
                current_chunk_num = (start_idx // chunk_size) + 1
                total_chunks = (total_cuts + chunk_size - 1) // chunk_size
                
                print(f"Generating Chunk {current_chunk_num}/{total_chunks} (Cuts {start_idx+1}-{end_idx})...")
                
                # Load prompt template
                system_prompt = config.get("prompts", {}).get("story_chunk_generation", "")
                if not system_prompt:
                    system_prompt = DEFAULT_PROMPTS.get("story_chunk_generation", "")
                
                # Prepare Template
                system_prompt = system_prompt.replace("{{story_title}}", draftTitle or "")
                system_prompt = system_prompt.replace("{{start_cut}}", str(start_idx + 1))
                system_prompt = system_prompt.replace("{{end_cut}}", str(end_idx))
                system_prompt = system_prompt.replace("{{previous_context}}", previous_context_summary[-1000:]) # Keep last 1000 chars context
                system_prompt = system_prompt.replace("{{chunk_size}}", str(end_idx - start_idx))
                system_prompt = system_prompt.replace("{{atmosphere}}", str(draftSummary)) # Use summary/atmosphere

                max_retries = 3
                retry_count = 0
                chunk_success = False
                
                while retry_count < max_retries and not chunk_success:
                    try:
                        if retry_count > 0:
                            print(f"Retrying Chunk {current_chunk_num} (Attempt {retry_count+1})...")
                        
                        user_input = f"Generate cuts {start_idx+1} to {end_idx}. Focus on sequential flow. Output valid JSON."
                        
                        # Using synchronous call inside thread for this chunk
                        response = await asyncio.to_thread(
                            client.chat.completions.create,
                            model="gpt-5-mini-2025-08-07",
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_input}
                            ],
                            response_format={"type": "json_object"}
                        )
                        
                        content = response.choices[0].message.content
                        
                        # Parse Chunk
                        chunk_json = json.loads(content)
                        chunk_cuts = chunk_json.get("cuts", [])
                        
                        if not chunk_cuts:
                            raise ValueError("No cuts returned in JSON")

                        # Validate and fix cut numbers
                        for i, cut in enumerate(chunk_cuts):
                            if "description" not in cut:
                                raise ValueError(f"Missing 'description' in cut {start_idx + 1 + i}")
                            
                            cut["cutNumber"] = start_idx + 1 + i
                            cut["characterTag"] = "The Wild Animal" # Force tag again
                        
                        generated_cuts.extend(chunk_cuts)
                        
                        # Stream this chunk to frontend
                        chunk_text_representation = f"\n[Chunk {current_chunk_num}]\n"
                        for cut in chunk_cuts:
                            chunk_text_representation += f"{cut['cutNumber']}. {cut['description']}\n"
                            if 'imagePrompt' in cut:
                                chunk_text_representation += f"   [Image Prompt]: {cut['imagePrompt'][:50]}...\n"
                        
                        yield {"event": "delta", "data": json.dumps({"text": chunk_text_representation})}
                        
                        # Update Context for next loop
                        last_cut_desc = chunk_cuts[-1]['description'] if chunk_cuts else ""
                        previous_context_summary += f"\n[Chunk {current_chunk_num} Summary]: Ends with {last_cut_desc}"
                        
                        chunk_success = True
                        
                    except Exception as parse_e:
                        retry_count += 1
                        print(f"Chunk parse error (Attempt {retry_count}): {parse_e}")
                        yield {"event": "delta", "data": json.dumps({"text": f"\n[Error parsing chunk {current_chunk_num}... Retrying ({retry_count}/{max_retries})]\n"})}
                        
                        if retry_count >= max_retries:
                            yield {"event": "delta", "data": json.dumps({"text": f"\n[Failed Chunk {current_chunk_num} after retries. Manual review required.]\n"})}

            # Final Complete Event with ALL cuts
            full_text = "\n".join([f"{c['cutNumber']}. {c['description']}" for c in generated_cuts])
            
            yield {"event": "complete", "data": json.dumps({
                "cuts": generated_cuts,
                "characterPrompt": "The Wild Animal (Detailed in Config)",
                "fullText": full_text,
                "source": "openai_chain"
            })}
            
        except Exception as e:
            print(f"Streaming Error: {e}")
            import traceback
            traceback.print_exc()
            yield {"event": "error", "data": json.dumps({"error": f"API Error: {str(e)}", "detail": str(e)})}

    return EventSourceResponse(event_generator())

# Global state for generation control
generation_state = {
    "status": "running" # running, stopped, finish_early
}

class ControlRequest(BaseModel):
    action: str # "stop" | "finish_early"

@app.post("/api/workflow/control")
async def control_generation(req: ControlRequest):
    global generation_state
    if req.action in ["stop", "finish_early"]:
        generation_state["status"] = req.action
        return {"status": "updated", "new_state": generation_state["status"]}
    return {"status": "ignored", "reason": "invalid_action"}

@app.post("/api/workflow/regenerate-cut")
async def regenerate_cut(req: RegenerateCutRequest):
    """Regenerate a single cut while maintaining story continuity"""
    config = load_config()
    client = get_openai_client()
    
    # If no API key, use mock data
    if not client:
        await asyncio.sleep(1)
        mock_cut = {
            "cutNumber": req.cutNumber,
            "description": f"[재생성됨] 컷 {req.cutNumber} - 새로운 장면 묘사가 생성되었습니다.",
            "characterTag": req.characterTag,
            "emotionLevel": 5,
            "cameraAngle": "eye_level",
            "lightingCondition": "natural_daylight",
            "weatherAtmosphere": "clear",
            "physicsDetail": "Standing firmly on ground, weight evenly distributed",
            "sfxGuide": "Ambient nature sounds, medium distance",
            "transitionHint": "cut"
        }
        return {"success": True, "cut": mock_cut, "source": "mock"}
    
    # Real OpenAI API call
    try:
        system_prompt = config.get("prompts", {}).get("single_cut_regeneration", "")
        if not system_prompt:
            system_prompt = config.get("prompts", {}).get("single_cut_regeneration", DEFAULT_PROMPTS.get("single_cut_regeneration", ""))
        
        # Always enforce imagePrompt requirement
        system_prompt += (
            "\n\n[CRITICAL] You MUST include 'imagePrompt' field with a detailed ENGLISH description "
            "optimized for Stable Diffusion image generation. Example: \"A red fox leaping through snow, muscles tensed, powder flying...\""
        )
        
        # Replace template variables
        system_prompt = system_prompt.replace("{{story_title}}", req.storyTitle)
        system_prompt = system_prompt.replace("{{character_tag}}", req.characterTag)
        system_prompt = system_prompt.replace("{{cut_number}}", str(req.cutNumber))
        system_prompt = system_prompt.replace("{{total_cuts}}", str(req.totalCuts))
        system_prompt = system_prompt.replace("{{emotion_range}}", req.emotionRange)
        
        prev_summary = "N/A (this is the first cut)" if not req.previousCut else req.previousCut.get("description", "N/A")
        next_summary = "N/A (this is the last cut)" if not req.nextCut else req.nextCut.get("description", "N/A")
        system_prompt = system_prompt.replace("{{previous_cut}}", prev_summary)
        system_prompt = system_prompt.replace("{{next_cut}}", next_summary)
        
        user_input = f"""Regenerate cut {req.cutNumber} of {req.totalCuts}.

Previous cut: {prev_summary}
Next cut: {next_summary}

Character: {req.characterTag}
Emotion range for this position: {req.emotionRange}

Generate a complete cut object with all required fields (cutNumber, description, characterTag, emotionLevel, cameraAngle, lightingCondition, weatherAtmosphere, physicsDetail, sfxGuide, transitionHint)."""
        
        response = client.responses.create(
            model="gpt-5-mini-2025-08-07",
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ]
        )
        
        output_text = response.output_text
        
        # Parse JSON
        json_match = re.search(r'\{.*\}', output_text, re.DOTALL)
        if json_match:
            cut = json.loads(json_match.group())
            cut["cutNumber"] = req.cutNumber  # Ensure correct cut number
            cut["characterTag"] = req.characterTag  # Ensure character tag consistency
        else:
            cut = {
                "cutNumber": req.cutNumber,
                "description": output_text[:500],
                "characterTag": req.characterTag,
                "emotionLevel": 5,
                "cameraAngle": "eye_level",
                "lightingCondition": "natural_daylight",
                "weatherAtmosphere": "clear",
                "physicsDetail": "Generated from text",
                "sfxGuide": "Ambient sounds",
                "transitionHint": "cut"
            }
        
        return {"success": True, "cut": cut, "source": "openai"}
    except Exception as e:
        print(f"OpenAI Regenerate Cut Error: {e}")
        return {"success": False, "error": str(e)}

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
        system_prompt = config.get("prompts", {}).get("title_generation", "한국 콘텐츠 마케팅 전문가입니다. 스토리 분석 후 한국어 제목 8개를 JSON 배열로 반환하세요.")
        
        # Force strict Korean instruction
        system_prompt += "\n\n[CRITICAL REQUEST] All titles must be in KOREAN (한국어). Do NOT generate English titles."
        
        response = client.responses.create(
            model="gpt-5-mini-2025-08-07",
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
        "image_filename": "animal_protagonist_wide.png" if mode == "Long Form (16:9)" else "animal_protagonist_tall.png",
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
            
            thumbnails = [f"/outputs/{urllib.parse.quote(folder_name)}/{img}" for img in images[:3]]
            
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
        return {"error": "Project not found"}
        
    images = sorted([f for f in os.listdir(folder_path) if f.endswith(('.png', '.jpg'))])
    assets = [f"/outputs/{urllib.parse.quote(folder_name)}/{img}" for img in images]
    
    meta_path = os.path.join(folder_path, "metadata.json")
    metadata = {}
    if os.path.exists(meta_path):
        with open(meta_path, 'r') as f:
            metadata = json.load(f)
            
    return {
        "title": metadata.get("title", folder_name),
        "folder_name": folder_name,
        "assets": assets,
        "metadata": metadata
    }

@app.delete("/api/history/{folder_name}")
async def delete_project(folder_name: str):
    try:
        folder_path = os.path.join(OUTPUTS_DIR, folder_name)
        if os.path.exists(folder_path):
            import shutil
            shutil.rmtree(folder_path)
            return {"success": True}
        return {"success": False, "error": "Folder not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/workflow/history/{folder_name}/generate_veo_prompts")
async def generate_veo_prompts_for_history(folder_name: str):
    """Generate Veo 3.1 prompts for an existing project using saved cut data"""
    try:
        import urllib.parse
        folder_name = urllib.parse.unquote(folder_name) # Ensure decoded
        folder_path = os.path.join(OUTPUTS_DIR, folder_name)
        meta_path = os.path.join(folder_path, "metadata.json")
        
        if not os.path.exists(folder_path) or not os.path.exists(meta_path):
            return {"success": False, "error": "Project metadata not found"}
            
        config = load_config()
        client = get_openai_client()
        
        with open(meta_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
            
        cuts_data = metadata.get("cuts_data", [])
        if not cuts_data:
            return {"success": False, "error": "No cut data found in metadata. Cannot regenerate."}
            
        updated_cuts = []
        veo_prompt_template = config.get("prompts", {}).get("veo_video", "")
        
        for cut in cuts_data:
            # Need strict fields for Veo prompt
            # If sfxGuide is missing, we might need to infer or make empty
            if "sfxGuide" not in cut: 
                cut["sfxGuide"] = "Natural ambiance"
                
            if "videoPrompt" not in cut or not cut["videoPrompt"]:
                # Generate Prompt
                try:
                    prompt_text = veo_prompt_template
                    # Replace standard keys
                    prompt_text = prompt_text.replace("{{cut_number}}", str(cut.get("cutNumber", "")))
                    prompt_text = prompt_text.replace("{{scene_description}}", cut.get("description", ""))
                    prompt_text = prompt_text.replace("{{character_tag}}", cut.get("characterTag", "The Character"))
                    prompt_text = prompt_text.replace("{{emotion_level}}", str(cut.get("emotionLevel", "5")))
                    prompt_text = prompt_text.replace("{{physics_detail}}", cut.get("physicsDetail", "None"))
                    prompt_text = prompt_text.replace("{{sfx_guide}}", cut.get("sfxGuide", "None"))
                    
                    # Call LLM for refinement
                    response = client.responses.create(
                        model="gpt-5-mini-2025-08-07",
                        input=[
                            {"role": "system", "content": "You are a prompt engineer. Output strictly the filled prompt."},
                            {"role": "user", "content": f"Complete this template:\n\n{prompt_text}"}
                        ]
                    )
                    cut["videoPrompt"] = response.output_text.strip()
                    cut["veo_generated"] = True
                except Exception as e:
                     print(f"Error generating Veo prompt for cut {cut.get('cutNumber')}: {e}")
                     cut["videoPrompt"] = "Generation Failed"
            
            updated_cuts.append(cut)
            
        # Save back
        metadata["cuts_data"] = updated_cuts
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=4, ensure_ascii=False)
            
        return {"success": True, "updated_cuts": updated_cuts}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

# ==========================================
# [Helpers] SSE & Utils
# ==========================================
def create_sse_event(data: dict):
    # USE ensure_ascii=True for maximum safety (escapes all non-ASCII as \uXXXX)
    # This is the most robust way to prevent "Invalid Control Character" errors in browsers
    json_str = json.dumps(data, ensure_ascii=True)
    return f"data: {json_str}\n\n"

def get_time():
    return time.strftime("%H:%M:%S")

def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", name).replace(" ", "_")

# ==========================================
# [Mock Generator] SSE Stream
# ==========================================
async def mock_comfyui_process_generator(params: dict, topic: str) -> AsyncGenerator[str, None]:
    
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
    yield create_sse_event({"type": "result", "data": result_data})
    yield create_sse_event({"type": "done"})

# ==========================================
# [Queue System] For passing large data to Stream
# ==========================================
generation_jobs = {}

class QueueRequest(BaseModel):
    mode: str
    topic: str
    cuts: List[dict]
    concept: str = "Default"
    title: str = ""
    characterPrompt: str = ""

@app.post("/api/queue-generation")
async def queue_generation(req: QueueRequest):
    job_id = str(uuid.uuid4())
    generation_jobs[job_id] = req.dict()
    return {"success": True, "jobId": job_id}

@app.get("/api/stream")
async def stream_workflow(mode: str = "long", topic: str = "", cuts: int = 20, concept: str = "Default", title: str = "", referenceImage: str = "", jobId: str = ""):
    # Check key from Queue
    job_data = {}
    if jobId and jobId in generation_jobs:
        job_data = generation_jobs[jobId]
        # Override params with job data
        mode = job_data.get("mode", mode)
        topic = job_data.get("topic", topic)
        cuts = len(job_data.get("cuts", [])) or cuts
        concept = job_data.get("concept", concept)
        title = job_data.get("title", title)
    
    params = calculate_parameters(mode, concept, cuts, title)
    
    # Inject full cuts data into params if available
    if job_data:
        params['cuts_data'] = job_data.get("cuts", [])
        params['character_prompt'] = job_data.get("characterPrompt", "")

    # Use real generator by default, which has internal fallback or error handling
    return StreamingResponse(
        real_comfyui_process_generator(params, topic, referenceImage), 
        media_type="text/event-stream"
    )

def check_comfyui_connection(host="127.0.0.1", port=8188):
    """Check if ComfyUI server is reachable"""
    import socket
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except (socket.timeout, ConnectionRefusedError):
        return False
    except Exception:
        return False

import subprocess

async def real_comfyui_process_generator(params: dict, topic: str, reference_image: str = "") -> AsyncGenerator[str, None]:
    """
    Real ComfyUI generation process:
    1. Check connection
    2. Create project folder
    3. Loop through cuts and generate images via ComfyUI
    """
    # 1. Connection Check
    if not check_comfyui_connection():
        yield create_sse_event({"type": "error", "message": "❌ ComfyUI 서버(127.0.0.1:8188)가 켜져있지 않습니다. 실행 후 다시 시도해주세요."})
        yield create_sse_event({"type": "done"})
        return
    
    # [REVERTED] IP-Adapter Auto-Install and Reference Image Logic removed by user request.

    config = load_config()
    comfyui_server = "127.0.0.1:8188"
    client = ComfyUIClient(comfyui_server)
    
    # 2. Setup Project
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    folder_name = f"{timestamp}_{sanitize_filename(params['selected_title'] or topic)}"
    project_dir = os.path.join(OUTPUTS_DIR, folder_name)
    os.makedirs(project_dir, exist_ok=True)
    
    total_cuts = params['total_cuts']
    
    # [CONTROL] Reset state at start
    global generation_state
    generation_state["status"] = "running"
    
    yield create_sse_event({"type": "log", "message": f"🚀 프로젝트 생성: {folder_name}"})
    yield create_sse_event({"type": "log", "message": f"📸 총 {total_cuts}컷 이미지 생성 시작 (Real ComfyUI)"})

    # Load Workflow Template
    workflow_template = load_workflow_template("base_generation")
    if not workflow_template:
        yield create_sse_event({"type": "error", "message": "❌ 기본 워크플로우(base_generation.json)를 찾을 수 없습니다."})
        return
        
    # Get selected model
    selected_model = config.get("selected_model", "RealVisXL_V5.0.safetensors")
    
    # [Smart Fallback] Check if model exists, otherwise use first available
    available_models = await fetch_available_models(config)
    if available_models:
        if selected_model not in available_models:
            fallback_model = available_models[0]
            yield create_sse_event({"type": "log", "message": f"⚠️ 모델 '{selected_model}'을(를) 찾을 수 없어 '{fallback_model}'을(를) 사용합니다."})
            selected_model = fallback_model

    # 3. Generation Loop
    
    # [REVERTED] Reference Image & IP-Adapter Injection Logic removed.
    # if reference_image and os.path.exists(reference_image):
    #     ...

    generated_images = []
    cuts_data = params.get("cuts_data", [])
    
    for i, current_cut in enumerate(cuts_data):
        # [CONTROL] Check State
        if generation_state["status"] == "stopped":
            yield create_sse_event({"type": "log", "message": "🛑 사용자 요청으로 생성이 중단되었습니다."})
            yield create_sse_event({"type": "error", "message": "Generation Stopped"}) # Frontend handles this
            generation_state["status"] = "idle" # Reset state
            return
            
        elif generation_state["status"] == "finish_early":
            yield create_sse_event({"type": "log", "message": "🏁 사용자 요청으로 조기 종료합니다. (현재까지 생성된 이미지만 저장)"})
            generation_state["status"] = "idle" # Reset state
            break # Break loop, proceed to DONE
            
        cut_number = current_cut.get("cutNumber", i+1)
        yield create_sse_event({"type": "log", "message": f"⏳ [Cut {cut_number}/{total_cuts}] 생성 중...", "cutIndex": cut_number})
        
        try:
            # Prepare Prompt
            if current_cut:
                # Construct detailed prompt from story data
                # 1. Use specific English Image Prompt if available (Best)
                if current_cut.get("imagePrompt"):
                    # Sanitize: remove control characters and newlines
                    positive_prompt = clean_string(current_cut.get('imagePrompt', ''))
                else:
                    # 2. Fallback: Construct from other fields
                    desc = clean_string(current_cut.get("description", ""))
                    physics = clean_string(current_cut.get("physicsDetail", ""))
                    lighting = clean_string(current_cut.get("lightingCondition", ""))
                    weather = clean_string(current_cut.get("weatherAtmosphere", ""))
                    # Only include character prompt if character tag is present or appropriate
                    char_prompt = clean_string(params.get("character_prompt", "")) if current_cut.get("characterTag") else ""
                    
                    # Use template from config
                    positive_template = config.get("prompts", {}).get("positive_prompt_template", "photorealistic, 8K UHD, {{scene}}")
                    scene_text = f"{desc}, {physics}, {lighting}, {weather}, {char_prompt}"
                    positive_prompt = positive_template.replace("{{scene}}", scene_text)
            else:
                # Fallback to generic prompt
                positive_template = config.get("prompts", {}).get("positive_prompt_template", "photorealistic, 8K UHD, {{scene}}")
                positive_prompt = positive_template.replace("{{scene}}", f"{topic}, scene {i}")

            # Get negative prompt from config and clean it
            raw_neg = config.get("prompts", {}).get("negative_prompt", "bad quality, blurry, text, watermark")
            negative_prompt = clean_string(raw_neg)

            # [Veo 3.1 Integration] Generate 5-Element Video Prompt
            veo_prompt_text = ""
            if current_cut:
                try:
                    veo_system = config.get("prompts", {}).get("veo_video", "")
                    if veo_system:
                         # Replace template variables
                        veo_system = veo_system.replace("{{scene_description}}", current_cut.get("description", ""))
                        veo_system = veo_system.replace("{{physics_detail}}", current_cut.get("physicsDetail", "Dynamic movement"))
                        veo_system = veo_system.replace("{{sfx_guide}}", current_cut.get("sfxGuide", "Ambient sound"))
                        veo_system = veo_system.replace("{{emotion_level}}", str(current_cut.get("emotionLevel", 5)))
                        veo_system = veo_system.replace("{{character_tag}}", current_cut.get("characterTag", "Main Character"))
                        
                        # We use a separate non-streaming call for this metadata generation
                        openai_client = get_openai_client()
                        if openai_client:
                             veo_resp = await asyncio.to_thread(
                                openai_client.chat.completions.create,
                                model="gpt-5-mini-2025-08-07",
                                messages=[
                                    {"role": "system", "content": veo_system},
                                    {"role": "user", "content": "Generate 5-element Veo prompt."}
                                ]
                            )
                             veo_prompt_text = veo_resp.choices[0].message.content
                except Exception as e:
                    print(f"Veo Prompt Gen Error: {e}")
                    veo_prompt_text = f"Failed to generate Veo prompt: {e}"

            import random
            seed = random.randint(0, 2**32 - 1)
            
            workflow = prepare_workflow(workflow_template, {
                "positive_prompt": positive_prompt,
                "negative_prompt": negative_prompt,
                "seed": seed,
                "cut_number": i,
                "ckpt_name": selected_model
            })
            
            # Queue Prompt
            result = client.queue_prompt(workflow)
            prompt_id = result.get("prompt_id")
            
            if not prompt_id:
                yield create_sse_event({"type": "log", "message": f"⚠️ [Cut {i}] 큐 추가 실패"})
                continue
                
            # Wait for Generation
            max_wait = 120
            start_time = time.time()
            image_saved = False
            
            while time.time() - start_time < max_wait:
                history = client.get_history(prompt_id)
                if prompt_id in history:
                    outputs = history[prompt_id].get("outputs", {})
                    for node_id, node_output in outputs.items():
                        if "images" in node_output:
                            image_info = node_output["images"][0]
                            image_data = client.get_image(
                                image_info["filename"],
                                image_info.get("subfolder", ""),
                                image_info.get("type", "output")
                            )
                            
                            # Save to project folder
                            filename = f"cut_{i:03d}_{seed}.png"
                            filepath = os.path.join(project_dir, filename)
                            with open(filepath, 'wb') as f:
                                f.write(image_data)
                                
                            # [Veo 3.1 Integration] Save Video Prompt Text
                            if veo_prompt_text:
                                txt_filename = f"cut_{i:03d}_{seed}.txt"
                                txt_filepath = os.path.join(project_dir, txt_filename)
                                with open(txt_filepath, 'w', encoding='utf-8') as tf:
                                    tf.write(veo_prompt_text)

                            generated_images.append(filename)
                            image_saved = True
                            
                            # Stream Preview
                            with open(filepath, "rb") as img_file:
                                b64_data = base64.b64encode(img_file.read()).decode('utf-8')
                                yield create_sse_event({
                                    "type": "preview",
                                    "image": f"data:image/png;base64,{b64_data}",
                                    "cutIndex": i
                                })

                            yield create_sse_event({"type": "log", "message": f"✅ [Cut {i}] 생성 완료: {filename}"})
                            
                            # [Advanced] Force Memory Cleanup
                            client.free_memory()
                            
                            # If this is the last cut, we can maybe show a preview
                            if i == total_cuts:
                                pass
                                
                    break # Break wait loop
                await asyncio.sleep(1)
            
            if not image_saved:
                yield create_sse_event({"type": "log", "message": f"⚠️ [Cut {i}] 시간 초과"})
                
        except Exception as e:
            yield create_sse_event({"type": "log", "message": f"⚠️ [Cut {i}] 에러: {str(e)}"})
            await asyncio.sleep(1)

    # 4. Finalize
    import urllib.parse
    first_image_encoded = urllib.parse.quote(generated_images[0]) if generated_images else ""
    
    # [METADATA UPDATE] Save full cuts info including prompts
    # Re-construct full cuts list with generated filenames
    final_cuts_metadata = []
    cuts_data = params.get("cuts_data", [])
    
    for i, cut in enumerate(cuts_data):
        # Find if this cut was generated
        cut_num = cut.get("cutNumber", i+1)
        # Try to find matching image
        img_name = f"{cut_num:03d}.png"
        if img_name in generated_images:
            cut_copy = cut.copy()
            cut_copy["filename"] = img_name
            final_cuts_metadata.append(cut_copy)

    result_data = {
        "title": params['selected_title'] or topic,
        "mode": params['mode_name'],
        "resolution": f"{params['resolution_w']}x{params['resolution_h']}",
        "cuts": len(generated_images),
        "created_at": get_time(),
        "image_url": f"/outputs/{urllib.parse.quote(folder_name)}/{first_image_encoded}" if generated_images else "",
        "assets": [f"/outputs/{urllib.parse.quote(folder_name)}/{img}" for img in generated_images],
        "cuts_data": final_cuts_metadata # Save prompts here
    }
    
    with open(os.path.join(project_dir, "metadata.json"), 'w') as f:
        json.dump(result_data, f)

    yield create_sse_event({"type": "log", "message": f"✅ 모든 이미지 생성 완료. ({len(generated_images)}/{total_cuts})"})
    yield create_sse_event({"type": "result", "data": result_data})
    yield create_sse_event({"type": "done"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3501)
