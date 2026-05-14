from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .core.database import Base, engine
from .routers import (
    alerts,
    auth,
    compte_rendus,
    dashboard,
    github,
    jira,
    merge_requests,
    projects,
    scores,
    webhooks,
)

Base.metadata.create_all(bind=engine)
app = FastAPI(
    title=settings.project_name,
    openapi_url=f"{settings.api_v1_str}/openapi.json"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router, prefix=settings.api_v1_str)
app.include_router(github.router, prefix=settings.api_v1_str)
app.include_router(jira.router, prefix=settings.api_v1_str)
app.include_router(webhooks.router, prefix=settings.api_v1_str)
app.include_router(projects.router, prefix=settings.api_v1_str)
app.include_router(alerts.router, prefix=settings.api_v1_str)
app.include_router(dashboard.router, prefix=settings.api_v1_str)
app.include_router(scores.router, prefix=settings.api_v1_str)
app.include_router(merge_requests.router, prefix=settings.api_v1_str)
app.include_router(compte_rendus.router, prefix=settings.api_v1_str)
@app.get("/")
def root() -> dict[str, str]:
    return {"message": "FastAPI Backend is running", "docs": "/docs"}
@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status":"healthy", "service": settings.project_name}
