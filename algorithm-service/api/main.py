import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import health_router, pathfinding_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

app = FastAPI(
    title="Algorithm Service",
    description="Pathfinding service for robot navigation",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(pathfinding_router)


@app.get("/")
async def root():
    return {
        "service": "Algorithm Service",
        "version": "0.1.0",
        "docs": "/docs"
    }
