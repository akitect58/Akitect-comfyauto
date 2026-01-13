import uuid
from fastapi import APIRouter
from fastapi.responses import Response
from sse_starlette.sse import EventSourceResponse
from backend.core.schemas import (
    DraftRequest, RegenerateDraftRequest, StoryRequest, 
    PrepareStoryRequest, RegenerateCutRequest, TitleRequest, 
    ParseScriptRequest, QueueRequest, ControlRequest, 
    ReferenceImageRequest, UploadRequest
)
from backend.services.openai_service import (
    generate_drafts, generate_drafts_stream, generate_drafts_parallel, regenerate_draft,
    generate_story, prepare_story_generation, story_generation_stream,
    regenerate_cut, generate_titles, parse_script
)
from backend.services.generation import (
    real_comfyui_process_generator, upload_reference, generate_reference_image,
    set_generation_status, get_generation_status
)
from backend.services.comfyui_service import calculate_parameters

router = APIRouter(prefix="/api", tags=["workflow"])

# Workflow: Drafts & Story
router.add_api_route("/workflow/drafts", generate_drafts, methods=["POST"])
router.add_api_route("/workflow/drafts/stream", generate_drafts_stream, methods=["GET"])
router.add_api_route("/workflow/drafts/parallel", generate_drafts_parallel, methods=["GET"])
router.add_api_route("/workflow/draft/regenerate", regenerate_draft, methods=["POST"])

router.add_api_route("/workflow/story", generate_story, methods=["POST"])
router.add_api_route("/workflow/story/prepare", prepare_story_generation, methods=["POST"])
router.add_api_route("/workflow/story/stream", story_generation_stream, methods=["GET"])
router.add_api_route("/workflow/story/parse", parse_script, methods=["POST"])
router.add_api_route("/workflow/regenerate-cut", regenerate_cut, methods=["POST"])

router.add_api_route("/workflow/titles", generate_titles, methods=["POST"])

# Workflow: Reference & Generation
router.add_api_route("/workflow/upload_reference", upload_reference, methods=["POST"])
router.add_api_route("/workflow/generate-reference", generate_reference_image, methods=["POST"])

# Queue System
generation_jobs = {}

@router.post("/queue-generation")
async def queue_generation(req: QueueRequest):
    job_id = str(uuid.uuid4())
    generation_jobs[job_id] = req.dict()
    return {"success": True, "jobId": job_id}

@router.get("/stream")
async def stream_workflow(
    mode: str = "long", 
    topic: str = "", 
    cuts: int = 20, 
    concept: str = "Default", 
    title: str = "", 
    referenceImage: str = "", 
    jobId: str = ""
):
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
        
        # Use reference image from job if available (Logic update)
        if job_data.get("referenceImage"):
            referenceImage = job_data.get("referenceImage")
    
    params = calculate_parameters(mode, concept, cuts, title)
    
    # Inject full cuts data into params if available
    params['cuts'] = job_data.get("cuts", [])
    params['character_prompt'] = job_data.get("characterPrompt", "")
    params['style'] = job_data.get("style", "photoreal")

    # Use real generator
    return EventSourceResponse(
        real_comfyui_process_generator(params, topic, referenceImage)
    )

@router.post("/workflow/control")
async def control_generation(req: ControlRequest):
    if req.action in ["stop", "finish_early"]:
        if set_generation_status(req.action):
             return {"success": True, "status": "updated", "new_state": req.action}
    return {"success": False, "error": "invalid_action or failed to update"}
