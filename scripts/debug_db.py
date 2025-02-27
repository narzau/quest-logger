# scripts/debug_db.py
import os
import sys

# Add the project root directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.config import settings

if __name__ == "__main__":
    print("Database URL:", str(settings.SQLALCHEMY_DATABASE_URI))
    sys.stdout.flush()