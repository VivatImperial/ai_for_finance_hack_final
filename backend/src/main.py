from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

import structlog
from fastapi import APIRouter, FastAPI
from sqlalchemy import text
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from config import settings
from db.base import init_db, engine, session_factory
from db.repositories.user_repo import create_default_admin
from internal.dependencies import Db
from internal.routers import auth_router, chat_router, document_router
from internal.routers.admin import setup_admin
from setup_logger import setup_logging
from services.rag.prompt_registry import seed_prompts

setup_logging(log_level=settings.LOG_LEVEL)
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, Any]:
    logger.info("Application starting up")

    try:
        logger.info("Initializing database connection")
        await init_db()
        logger.info("Database initialized successfully")
        if settings.ADD_BASE_ADMIN:
            await create_default_admin()

        async with session_factory() as session:
            await seed_prompts(session)
            await session.commit()

        yield

    except Exception:
        logger.error("Application startup failed", exc_info=True)
        raise

    finally:
        logger.info("Application shutting down")


app = FastAPI(lifespan=lifespan)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router.router)
api_router.include_router(chat_router.router)
api_router.include_router(document_router.router)


app.include_router(api_router)
admin = setup_admin(app, engine)


@app.get("/health", include_in_schema=False)
async def health_check(db: Db) -> JSONResponse:
    try:
        logger.info("health-check", endpoint="/health")
        await db.execute(text("SELECT 1"))
        return JSONResponse({"status": "healthy"}, status_code=200)
    except Exception as e:
        return JSONResponse({"status": "unhealthy", "error": str(e)}, 503)


@app.exception_handler(Exception)
async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "error": f"Internal Server Error: {exc!s}",
            "message": "An unexpected error occurred",
        },
    )
