"""
BookScout AI - Main Application Entry Point
FastAPI server with SSE endpoint for agentic book research.
"""

import json
import logging
import asyncio

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from backend.models.schemas import UserQuery, AgentStatus
from backend.agents.orchestrator import AgentOrchestrator
from backend.config import settings

# ─── Logging Setup ────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("bookscout")

# ─── FastAPI App ──────────────────────────────────────────────
app = FastAPI(
    title="BookScout AI",
    description="AI Book Research Assistant - Research books before you invest your time and money.",
    version="1.0.0",
)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")
templates = Jinja2Templates(directory="frontend/templates")


# ─── Routes ───────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serve the main landing page."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/research")
async def research_books(query: UserQuery):
    """
    Main research endpoint.
    Accepts a user query and streams agent status updates via SSE.
    The final event contains the complete recommendation data.
    """

    async def event_stream():
        """Generator that yields SSE events as agents process."""
        queue: asyncio.Queue[AgentStatus] = asyncio.Queue()

        async def status_callback(status: AgentStatus):
            """Callback passed to the orchestrator to emit status updates."""
            await queue.put(status)

        async def run_orchestrator():
            """Run the orchestrator and signal completion."""
            try:
                orchestrator = AgentOrchestrator()
                result = await orchestrator.run(query.query, status_callback)

                # Send final result
                final_status = AgentStatus(
                    agent="recommendation",
                    status="completed",
                    message="Research complete! Here are your recommendations.",
                    emoji="✅",
                    data=result.model_dump() if result else None,
                )
                await queue.put(final_status)
            except Exception as e:
                logger.error(f"Orchestrator error: {e}", exc_info=True)
                error_status = AgentStatus(
                    agent="system",
                    status="error",
                    message=f"An error occurred: {str(e)}",
                    emoji="❌",
                )
                await queue.put(error_status)
            finally:
                # Sentinel to end the stream
                await queue.put(None)

        # Start the orchestrator in a background task
        task = asyncio.create_task(run_orchestrator())

        try:
            while True:
                status = await queue.get()
                if status is None:
                    break

                event_data = status.model_dump()
                yield f"data: {json.dumps(event_data)}\n\n"

        except asyncio.CancelledError:
            task.cancel()
            raise

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/health")
async def health_check():
    """Health check endpoint that also verifies Ollama connectivity."""
    from backend.services.llm_service import LLMService

    llm = LLMService()
    ollama_ok = await llm.is_available()

    return {
        "status": "ok",
        "ollama": {
            "connected": ollama_ok,
            "url": settings.OLLAMA_BASE_URL,
            "model": settings.OLLAMA_MODEL,
        },
    }


# ─── Entry Point ──────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
    )
