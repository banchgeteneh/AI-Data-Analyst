import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.api.router import api_router
from app.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.database import check_database_connection


configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    try:
        check_database_connection()
        logger.info("Database connection verified")
    except SQLAlchemyError as error:
        logger.warning(
            "Database connection check failed (%s); database-backed requests may be unavailable.",
            type(error).__name__,
        )
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    application = FastAPI(
        title=app_settings.app_name,
        debug=app_settings.debug,
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.allowed_frontend_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.exception_handler(OperationalError)
    async def database_unavailable(_: Request, error: OperationalError) -> JSONResponse:
        logger.error("Database operation failed (%s).", type(error.orig).__name__)
        return JSONResponse(
            status_code=503,
            content={
                "detail": (
                    "Database unavailable. Verify the deployment's DATABASE_URL and "
                    "database credentials, then retry."
                )
            },
        )

    @application.exception_handler(SQLAlchemyError)
    async def database_error(_: Request, error: SQLAlchemyError) -> JSONResponse:
        logger.error("Database request failed (%s).", type(error).__name__)
        return JSONResponse(
            status_code=500,
            content={"detail": "A database operation could not be completed."},
        )

    application.include_router(api_router)
    return application


app = create_app()
