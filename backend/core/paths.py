import os

# Base Directory: backend/
# definitions: backend/core/paths.py -> parent -> backend/core -> parent -> backend
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ASSETS_DIR = os.path.join(BASE_DIR, "assets")
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

# Ensure directories exist
if not os.path.exists(OUTPUTS_DIR):
    os.makedirs(OUTPUTS_DIR)

if not os.path.exists(ASSETS_DIR):
    os.makedirs(ASSETS_DIR)
