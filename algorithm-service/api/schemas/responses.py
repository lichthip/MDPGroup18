from pydantic import BaseModel
from typing import List, Optional


class PathState(BaseModel):
    """Single state in the computed path."""
    x: int
    y: int
    d: int
    s: Optional[str] = None  # screenshot_id if this is a photo position


class PathfindingResponse(BaseModel):
    """Response body for successful /path requests."""
    path: List[PathState]
    commands: List[str]
    cost: float
    runtime: float


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    detail: Optional[str] = None


class HealthResponse(BaseModel):
    """Response for health check endpoint."""
    status: str
    version: str
