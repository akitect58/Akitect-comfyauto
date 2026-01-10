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
    "protagonist_prompt": '''20대 중반의 한국인 여성, 긴 검은 머리카락, 따뜻한 눈빛, 자연스러운 메이크업, 캐주얼한 차림새''',
    
    "style_animation": '''A vertical 16:9 semi-realistic digital portrait styled as a classic Korean folk tale illustration. It depicts {{subject_description}}. The background is a dreamy, misty landscape of rolling hills, ancient trees, and blooming wild plants, rendered with soft brushstrokes and a warm, golden-hour light that creates a gentle glow and a sense of mystery. The overall feel is calm, traditional, and mythical, with a textured, aged paper effect. --ar 9:16''',

    "negative_prompt_photoreal": '''cgi, 3d render, cartoon, anime, illustration, painting, drawing, art, 
digital art, concept art, artstation, deviantart,
vibrant colors, oversaturated, neon, glowing,
unnatural textures, perfect grooming, studio backdrop,
perfect lighting, studio lighting, rim lighting, 
fantasy, sci-fi, cyberpunk, magical, supernatural, mythical,
unrealistic proportions, anthropomorphic, talking characters,
blurry, low quality, low resolution, pixelated,
watermark, signature, text, logo, banner,
collage, multiple frames, split screen, border,
oversaturated, HDR, overprocessed, AI artifacts, 
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

    "formatted_draft_generation": '''You are a professional video storyteller.
[INPUT]
Category: {{category}}
Protagonist: {{protagonist}}

[TASK]
Generate 10 distinct story drafts.

[OUTPUT]
JSON array of objects with id, title, summary, theme, emotionalArc, visualStyle.
Ensure title and summary are in Korean.''',

    "draft_generation": '''You are a professional video storyteller.
[INPUT]
Category: {{category}}
Protagonist: {{protagonist}}

[TASK]
Generate {{count}} distinct story drafts.

[OUTPUT]
JSON array of objects with id, title, summary, theme, emotionalArc, visualStyle.
Ensure title and summary are in Korean.''',

    "story_confirmation": '''You are a professional video production screenwriter specialized in high-impact narrative storytelling.

[TASK]
Expand the selected story draft into exactly {{cut_count}} detailed cuts for video production.

[STORY CONTEXT]
Title: {{story_title}}
Summary: {{story_summary}}
Character Tag: {{character_tag}}

[CORE RULES]
1. MASTER CHARACTER TAG: Every cut MUST start with "{{character_tag}}" in the characterTag field
2. PHYSICS LOGIC: Specify physical interactions with concrete verbs (Grasping, Pushing, Stepping, Pressing)
3. HOOKING: Place the most dramatic scene in cuts 1-5 to maximize engagement
4. CHAIN PROMPTING: Summarize previous 10 cuts before generating next batch

[CUT STRUCTURE - Each cut requires:]
- cutNumber: Sequential number (1-{{cut_count}})
- description: Scene summary in Korean (2-3 sentences)
- characterTag: "{{character_tag}}" (MUST be identical across all cuts)
- emotionLevel: 1-10 scale (1=calm, 10=peak crisis)
- cameraAngle: ground_level | eye_level | high_angle | aerial | dutch_angle
- lightingCondition: natural_daylight | golden_hour | overcast | night | artificial | dramatic_shadows
- weatherAtmosphere: clear | rain | fog | snow | storm | dust | smoke
- physicsDetail: Specific physical interaction description
- sfxGuide: Sound design note (distance: near=crisp, far=muffled)
- transitionHint: cut | dissolve | fade | match_cut

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

    "master_character": '''You are a photorealistic image prompt specialist for SDXL/FLUX models.

[TASK]
Create a master character prompt that will be used across {{cut_count}} images for visual consistency.

[CHARACTER INPUT]
{{character_description}}

[FOCUS ELEMENTS - Be extremely specific:]
1. BODY: Exact breed/species, size, build, age indicators, posture tendency
2. FUR/SKIN: Color (use specific terms like "russet", "cream", "charcoal"), pattern, texture, sheen, condition (matted, clean, wet)
3. DISTINGUISHING MARKS: Scars, patches, unique colorations, missing fur areas
4. ACCESSORIES: Collar details (color, material, condition), tags, clothing if any
5. EXPRESSION BASELINE: Default ear position, eye characteristics, muzzle details

[FORBIDDEN]
- NO background descriptions
- NO action/movement descriptions
- NO lighting descriptions
- NO emotional states

[STYLE KEYWORDS TO INCLUDE]
photorealistic, 8K UHD, hyperdetailed fur texture, subsurface scattering, shot on Canon EOS R5, 85mm f/1.4

[OUTPUT]
Single paragraph, English only, comma-separated descriptors, optimized for SDXL/FLUX.''',

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

    "veo_video": '''You are a VEO 3.1 video prompt specialist following the 5-element formula.

[SCENE INPUT]
Cut Number: {{cut_number}}
Description: {{scene_description}}
Character Tag: {{character_tag}}
Emotion Level: {{emotion_level}}/10
Physics Detail: {{physics_detail}}
SFX Guide: {{sfx_guide}}

[5-ELEMENT FORMULA - Follow this exact order:]

1. CINEMATOGRAPHY
   - Lens by emotion: 1-4->35mm wide | 5-7->50mm medium | 8-10->85mm+ tight
   - Camera height: Animals->ground-level | Humans->eye-level
   - Movement: static | slow_pan | tracking | handheld | dolly | crane
   
2. SUBJECT
   - Reference as "{{character_tag}}" 
   - Current physical state, posture, visible condition
   
3. ACTION
   - Use present continuous tense
   - Include physics verbs: pressing, gripping, pushing, stepping, leaning
   - Specify contact points and pressure
   
4. CONTEXT
   - Location specifics, time of day
   - Weather particles between camera and subject (dirty frame technique)
   - Background movement/elements
   
5. STYLE & AMBIANCE
   - Lighting quality and direction
   - Color temperature (warm/cool/neutral)
   - SFX only (NO music, NO dialogue): {{sfx_guide}}

[MOTION CONTINUITY]
Previous cut ends with: {{previous_action}}
This cut should connect naturally from that state.

[FORBIDDEN]
- Background music references
- Dialogue or speech
- Text overlays
- Unrealistic camera movements

[OUTPUT]
Single paragraph English prompt following 5-element order, include [SFX: ...] tag at end.''',

    "title_generation": '''You are a viral content marketing specialist for English-speaking audiences.

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
1. Tension + Time: "48 Hours: The Final Stand"
2. Location + Crisis: "Lost in the Abyss: An Unlikely Escape"
3. Personal Stake: "The Secret That Changed Everything"
4. High Pursuit: "Across the Scorched Earth"
5. Triumph: "Against All Odds: The Rise from Shadows"

[REQUIREMENTS]
- Maximum 8 words per title
- Must work as YouTube/social video title
- Include emotional hook
- Avoid clichés like "Amazing", "Unbelievable", "You Won't Believe"

[OUTPUT FORMAT]
JSON array: [{"title": "English Title", "style": "category", "hook": "Why this works"}]''',

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
    """Parallel version: Generate 10 story drafts with 10 separate streaming API calls"""
    config = load_config()
    client = get_openai_client()
    
    async def event_generator():
        if not client:
            # Mock parallel simulation with streaming effect
            for i in range(10):
                draft_id = i + 1
                mock_text = f"Mock 스토리 #{draft_id} 생성 중... 병렬 처리 데모입니다."
                for char in mock_text:
                    yield {"event": "delta", "data": json.dumps({"draft_id": draft_id, "text": char})}
                    await asyncio.sleep(0.02)
                yield {"event": "draft", "data": json.dumps({
                    "id": draft_id,
                    "title": f"Mock Story {draft_id}",
                    "summary": mock_text,
                    "theme": "mock"
                })}
            yield {"event": "complete", "data": json.dumps({"total": 10, "source": "mock"})}
            return
        
        try:
            protagonist_prompt = config.get("prompts", {}).get("protagonist_prompt", "20대 중반의 한국인 여성")
            base_prompt = config.get("prompts", {}).get("draft_generation", "스토리 작가입니다.")
            base_prompt = base_prompt.replace("{{protagonist}}", protagonist_prompt)
            base_prompt = base_prompt.replace("{{category}}", category or "ALL")
            
            user_input = customInput if customInput else f"카테고리: {category}"
            
            # Queue to collect streaming events
            event_queue = asyncio.Queue()
            completed_count = [0]
            
            def sync_stream_single_draft(draft_id: int, queue_put):
                """Synchronous function to stream a single draft (runs in thread)"""
                try:
                    single_prompt = base_prompt.replace("{{count}}", "1")
                    single_prompt += f"\n\n지금 생성할 초안 번호: {draft_id}/10"
                    single_prompt += "\n반드시 단일 객체만 반환: {\"id\": " + str(draft_id) + ", \"title\": \"...\", \"summary\": \"...\", \"theme\": \"...\"}"
                    single_prompt += "\n[중요] summary와 title 모두 한국어로 작성하세요."
                    
                    # Non-streaming API call (simpler and more reliable)
                    response = client.responses.create(
                        model="gpt-5-mini-2025-08-07",
                        input=[
                            {"role": "system", "content": single_prompt},
                            {"role": "user", "content": user_input}
                        ]
                    )
                    
                    output_text = response.output_text
                    
                    # Send delta events character by character for UI
                    for char in output_text[:100]:  # First 100 chars for streaming effect
                        queue_put({"event": "delta", "data": json.dumps({"draft_id": draft_id, "text": char})})
                    
                    # Parse final JSON
                    json_match = re.search(r'\{.*\}', output_text, re.DOTALL)
                    if json_match:
                        draft = json.loads(json_match.group())
                        draft["id"] = draft_id
                    else:
                        draft = {"id": draft_id, "title": f"Story #{draft_id}", "summary": output_text[:400], "theme": "parsed"}
                    
                    queue_put({"event": "draft", "data": json.dumps(draft)})
                    return True
                except Exception as e:
                    queue_put({"event": "draft", "data": json.dumps({"id": draft_id, "title": f"Error #{draft_id}", "summary": str(e), "theme": "error"})})
                    return False
            
            # Use ThreadPoolExecutor for true parallelism with sync OpenAI calls
            import concurrent.futures
            loop = asyncio.get_event_loop()
            
            def blocking_put(item):
                asyncio.run_coroutine_threadsafe(event_queue.put(item), loop)
            
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)
            futures = [executor.submit(sync_stream_single_draft, i+1, blocking_put) for i in range(10)]
            
            # Wait for all to complete while yielding events
            done_count = 0
            while done_count < 10:
                # Check for completed futures
                for f in futures:
                    if f.done() and not hasattr(f, '_counted'):
                        f._counted = True
                        done_count += 1
                
                # Yield any queued events
                try:
                    event_data = await asyncio.wait_for(event_queue.get(), timeout=0.05)
                    yield event_data
                except asyncio.TimeoutError:
                    pass
                
                await asyncio.sleep(0.01)
            
            executor.shutdown(wait=False)
            
            # Drain remaining events
            await asyncio.sleep(0.1)  # Give a moment for final events
            while not event_queue.empty():
                event_data = await event_queue.get()
                yield event_data

            yield {"event": "complete", "data": json.dumps({"total": 10, "source": "openai_parallel_stream"})}

            
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
    # Get prompts
    protagonist_prompt = config.get("prompts", {}).get("protagonist_prompt", "20대 중반의 한국인 여성")
    
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
        
        # Always enforce imagePrompt requirement (override any config)
        image_prompt_instruction = (
            "\n\n[중요 추가 지침] 각 컷에는 반드시 'imagePrompt' 필드를 포함하세요. "
            "'imagePrompt'는 Stable Diffusion 이미지 생성용 **상세 영문 프롬프트**입니다. "
            "예: \"A woman kneeling in a collapsing shelter during a fierce storm, dramatic shadows, photorealistic, 8K UHD\""
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
            character_prompt = parsed.get("characterPrompt", "캐릭터 정보 없음")
        else:
            # Fallback: create simple cuts from text
            lines = output_text.split('\n')
            cuts = [{"cutNumber": i+1, "description": line[:200], "imagePrompt": f"Scene {i+1}, {req.draftTitle}"} for i, line in enumerate(lines[:total_cuts]) if line.strip()]
            character_prompt = "응답에서 캐릭터 정보를 파싱하지 못했습니다."
        
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
        try:
            print("Generating prompt...")
            system_prompt = config.get("prompts", {}).get("story_confirmation", "")
            
            if not system_prompt:
                system_prompt = config.get("prompts", {}).get("story_confirmation", DEFAULT_PROMPTS.get("story_confirmation", ""))
            else:
                # Correctly replace template variables based on DEFAULT_PROMPTS
                system_prompt = system_prompt.replace("{{cut_count}}", str(total_cuts))
                system_prompt = system_prompt.replace("{{story_title}}", draftTitle or "")
                system_prompt = system_prompt.replace("{{story_summary}}", draftSummary or "")
                system_prompt = system_prompt.replace("{{character_tag}}", "Main Character") 
            
            user_input = f"제목: {draftTitle}\n\n초안 요약:\n{draftSummary}\n\n위 초안을 바탕으로 {total_cuts}컷의 상세 스토리와 캐릭터 묘사를 생성해주세요."
            
            print(f"Calling OpenAI API (Model: gpt-5-mini-2025-08-07)...")
            
            # Using thread pool for synchronous OpenAI client streaming
            stream = await asyncio.to_thread(
                client.chat.completions.create,
                model="gpt-5-mini-2025-08-07",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input}
                ],
                stream=True
            )
            
            print("Stream started, receiving chunks...")

            full_text = ""
            for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    full_text += content
                    # print(f"Chunk received: {content[:10]}...") # Too verbose
                    yield {"event": "delta", "data": json.dumps({"text": content})}
            
            print("Stream finished. Parsing result...")
            
            # Parse the full text to extract cuts
            # Try to extract JSON array if present
            json_match = re.search(r'\{.*\}', full_text, re.DOTALL)
            if json_match:
                try:
                    parsed = json.loads(json_match.group())
                    cuts = parsed.get("cuts", [])
                    character_prompt = parsed.get("characterPrompt", "캐릭터 정보 없음")
                    print(f"JSON parsed successfully. Cuts: {len(cuts)}")
                except json.JSONDecodeError:
                    print("JSON parse failed, falling back to manual parsing")
                    lines = full_text.split('\n')
                    cuts = [{"cutNumber": i+1, "description": line[:200]} for i, line in enumerate(lines) if line.strip()][:total_cuts]
                    character_prompt = "캐릭터 정보 파싱 실패"
            else:
                print("No JSON found in response, using simple line splitting")
                # Fallback parsing
                lines = full_text.split('\n')
                cuts = [{"cutNumber": i+1, "description": line[:200]} for i, line in enumerate(lines) if line.strip()][:total_cuts]
                character_prompt = "응답에서 캐릭터 정보를 파싱하지 못했습니다."
            
            yield {"event": "complete", "data": json.dumps({
                "cuts": cuts,
                "characterPrompt": character_prompt,
                "fullText": full_text,
                "source": "openai"
            })}
            
        except Exception as e:
            print(f"Streaming Error: {e}")
            import traceback
            traceback.print_exc()
            yield {"event": "error", "data": json.dumps({"error": f"API Error: {str(e)}", "detail": str(e)})}

    return EventSourceResponse(event_generator())

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
            "optimized for Stable Diffusion image generation. Example: \"A woman kneeling in a collapsing shelter...\""
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
        system_prompt = config.get("prompts", {}).get("title_generation", "영미권 콘텐츠 마케팅 전문가입니다. 스토리 분석 후 영어 제목 8개를 JSON 배열로 반환하세요.")
        
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

    config = load_config()
    comfyui_server = "127.0.0.1:8188"
    client = ComfyUIClient(comfyui_server)
    
    # 2. Setup Project
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    folder_name = f"{timestamp}_{sanitize_filename(params['selected_title'] or topic)}"
    project_dir = os.path.join(OUTPUTS_DIR, folder_name)
    os.makedirs(project_dir, exist_ok=True)
    
    total_cuts = params['total_cuts']
    
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
    generated_images = []
    
    for i in range(1, total_cuts + 1):
        yield create_sse_event({"type": "log", "message": f"⏳ [Cut {i}/{total_cuts}] 생성 중...", "cutIndex": i})
        
        try:
            # Prepare Prompt
            cuts_data = params.get("cuts_data", [])
            current_cut = next((c for c in cuts_data if c.get("cutNumber") == i), None)
            
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
    result_data = {
        "title": params['selected_title'] or topic,
        "mode": params['mode_name'],
        "resolution": f"{params['resolution_w']}x{params['resolution_h']}",
        "cuts": len(generated_images),
        "created_at": get_time(),
        "image_url": f"/outputs/{folder_name}/{generated_images[0]}" if generated_images else ""
    }
    
    with open(os.path.join(project_dir, "metadata.json"), 'w') as f:
        json.dump(result_data, f)

    yield create_sse_event({"type": "log", "message": f"✅ 모든 이미지 생성 완료. ({len(generated_images)}/{total_cuts})"})
    yield create_sse_event({"type": "result", "data": result_data})
    yield create_sse_event({"type": "done"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3501)
