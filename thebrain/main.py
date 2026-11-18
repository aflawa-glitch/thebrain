"""Compatibility entry point for the fresh Julian rebuild."""
from app.main import app

if __name__ == "__main__":
    import uvicorn
    from app.core.config import settings
    uvicorn.run(app, host=settings.host, port=settings.port)
