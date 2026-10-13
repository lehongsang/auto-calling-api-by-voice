import os
import sys
import uvicorn

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.core.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=settings.PORT,
        reload=False,
        log_level="info",
    )
