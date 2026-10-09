from contextlib import asynccontextmanager

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import BACKEND_ROOT, settings
from app.routers import llm, papers


def run_migrations() -> None:
    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    command.upgrade(cfg, "head")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    run_migrations()
    yield


app = FastAPI(title="Reader API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(papers.router)
app.include_router(llm.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
