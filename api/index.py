import os
import sys

# Add the project root to the system path so all imports resolve
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Ensure the working directory is the project root so that
# Path("data/...") and Path("config.*") references work on Vercel
os.chdir(PROJECT_ROOT)

from dashboard_api import app

# This is required for Vercel to find the Flask app instance
# It must be named 'app'
