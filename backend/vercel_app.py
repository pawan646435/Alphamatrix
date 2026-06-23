import os
import sys

# Ensure the root of the backend folder is in python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.main import app

handler = app
