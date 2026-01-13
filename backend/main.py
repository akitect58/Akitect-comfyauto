import sys
import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Ensure we can import 'backend' package
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.paths import OUTPUTS_DIR, ASSETS_DIR, BASE_DIR
from backend.routers import workflow, settings, history

app = FastAPI()

# Input/Output Directories
if not os.path.exists(OUTPUTS_DIR):
    os.makedirs(OUTPUTS_DIR)
if not os.path.exists(ASSETS_DIR):
    os.makedirs(ASSETS_DIR)

# CORS config
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static Files
app.mount("/outputs", StaticFiles(directory=OUTPUTS_DIR), name="outputs")
app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")

# Include Routers
app.include_router(workflow.router)
app.include_router(settings.router)
app.include_router(history.router)
# (Optional) app.include_router(resources.router) if needed later

# Serve Frontend (Optional/Fallthrough)
# Check if frontend/dist exists to serve built files
frontend_dist = os.path.join(os.path.dirname(BASE_DIR), "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3501)
