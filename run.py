"""Launch the assistant: API + web UI on http://localhost:8000

    python run.py

The React UI is pre-built into frontend/dist (committed), so Node.js is only
needed if you want to change the frontend (see README).
"""

import sys

import uvicorn

from assistant.api import FRONTEND_DIST, create_app
from assistant.knowledge.retriever import get_retriever

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if not (FRONTEND_DIST / "index.html").exists():
        print("frontend/dist is missing. Build it once with:  cd frontend && npm install && npm run build")
        sys.exit(1)
    print("Loading the local embedding model and vector index (the first run downloads ~130 MB)...")
    get_retriever()  # warm up now, so the first question isn't slow
    app = create_app()
    print("Asterline Research Assistant -> http://localhost:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
