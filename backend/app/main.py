from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.router import api_router
from app.core.config import settings
from app.core.database import SessionLocal
from app.modules.identity.service import SeedService
from app.shared.storage import StorageException, get_storage_service


def create_app(seed_on_startup: bool = True) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if seed_on_startup:
            db = SessionLocal()
            try:
                SeedService(db).seed(settings.seed_admin_email, settings.seed_admin_password)
            finally:
                db.close()
        yield

    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", status_code=status.HTTP_200_OK, tags=["Health"])
    def health_check() -> dict[str, str]:
        return {"status": "healthy", "service": settings.app_name}

    @app.get("/health/db", status_code=status.HTTP_200_OK, tags=["Health"])
    def health_check_db() -> dict[str, str]:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            return {"status": "healthy", "database": "connected"}
        except Exception as exc:
            return {"status": "unhealthy", "database": str(exc)}
        finally:
            db.close()

    @app.get("/health/s3", status_code=status.HTTP_200_OK, tags=["Health"])
    def health_check_s3() -> dict[str, str]:
        if settings.app_env != "development":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
        try:
            get_storage_service().check_connectivity()
            return {
                "status": "healthy",
                "storage": "connected",
                "bucket": settings.aws_s3_bucket_name,
                "region": settings.aws_region,
            }
        except StorageException as exc:
            return {"status": "unhealthy", "storage": exc.message}

    app.include_router(api_router)

    return app


app = create_app()
