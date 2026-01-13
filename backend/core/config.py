import os
import json
from .paths import CONFIG_PATH

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

    "story_blueprint_generation": '''You are a master screenwriter planning a video production.
    
[TASK]
Create a detailed PLOT BLUEPRINT for a {{total_cuts}}-cut video, divided into {{total_chunks}} chunks of 10 cuts each.

[INPUT]
Title: {{story_title}}
Summary: {{story_summary}}
Theme: {{theme}}

[OUTPUT FORMAT]
JSON array of objects:
[
  {
    "chunkIndex": 1,
    "range": "1-10",
    "pacing": "SETUP/INTRO",
    "guide": "Detailed plot points...",
    "context": "Start: Parking Lot (Night). Rain starts.",
    "transition": "They leave the lot and enter the Alley."
  },
  ...
]

[CONSTRAINTS]
1. **LOGICAL PROGRESSION**: Ensure time and events flow naturally according to the story summary. Avoid unintended time loops (e.g., do not reset to 'Night' if the story moved to 'Day', unless the plot requires it).
2. **SCENE CONTINUITY**: Each chunk must mathematically follow the previous one. Chunk 2 starts EXACTLY where Chunk 1 ended.
3. **AVOID REPETITION**: Do not repeat the same scene beats or location descriptions unnecessarily. Progress the plot.
''',

    "story_chunk_generation": '''You are generating a specific chunk of a video screenplay. 
    
[CONTEXT]
Title: {{story_title}}
Current Chunk: Cuts {{start_cut}} to {{end_cut}}
Blueprint Guide: {{guide}}
Context: {{context}}
Atmosphere: {{atmosphere}}
Character Tag: The Wild Animal

[REQUIREMENTS]
- Generate exactly {{chunk_size}} cuts.
- **Start with cut number {{start_cut}}**.
- **Follow the Blueprint Guide strictly.**
- **FIELDS (MANDATORY)**:
  1. cutNumber (int)
  2. description (String, **KOREAN**): Visual scene summary.
  3. imagePrompt (String, **ENGLISH**): Optimized SDXL prompt. Focus on VISUALS. Format: "Subject, Action, Environment, Lighting, Camera Angle, Style, Tech Specs". Include keywords like "Close-up", "8k", "Best quality". **IMPORTANT: If human characters are present, they MUST be described as "Korean" or "East Asian".** 
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