import os
import sys

# Add the project root to the system path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dashboard_api import app

# This is required for Vercel to find the Flask app instance
# It must be named 'app'
