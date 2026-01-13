from pydantic import BaseModel
from typing import List, Dict, Optional

# Settings
class SettingsUpdate(BaseModel):
    openai_api_key: str | None = None
    comfyui_path: str | None = None
    use_reference_image: bool | None = None
    selected_model: str | None = None
    steps: int | None = None
    cfg: float | None = None
    sampler_name: str | None = None
    scheduler: str | None = None
    prompts: dict | None = None

# Drafts
class DraftRequest(BaseModel):
    mode: str
    category: str | None = None
    customInput: str | None = None

class RegenerateDraftRequest(BaseModel):
    draftId: int
    mode: str = "long"
    category: str | None = None
    customInput: str | None = None

# Story
class StoryRequest(BaseModel):
    mode: str
    draftId: int
    draftTitle: str
    draftSummary: str

class PrepareStoryRequest(BaseModel):
    draftId: int
    draftTitle: str
    draftSummary: str
    mode: str
    targetCuts: int | None = None

class RegenerateCutRequest(BaseModel):
    cutNumber: int
    totalCuts: int
    storyTitle: str
    characterTag: str
    previousCut: dict | None = None
    nextCut: dict | None = None
    emotionRange: str = "5-7"

class ParseScriptRequest(BaseModel):
    script: str
    mode: str = "long"

# Titles
class TitleRequest(BaseModel):
    storyPreview: str

# Workflow / Generation
class ReferenceImageRequest(BaseModel):
    mode: str
    style: str = "photoreal"
    cut: dict
    characterPrompt: str

class UploadRequest(BaseModel):
    image: str
    filename: str

class QueueRequest(BaseModel):
    mode: str
    style: str = "photoreal"
    topic: str
    cuts: List[dict]
    concept: str = "Default"
    title: str = ""
    characterPrompt: str = ""
    referenceImage: str = ""
    skip_generation: bool = False

class ControlRequest(BaseModel):
    action: str
