from pydantic import BaseModel, Field
from typing import List


class ObstacleRequest(BaseModel):
    """Single obstacle in a pathfinding request."""
    x: int = Field(..., ge=0, lt=20, description="X coordinate (0-19)")
    y: int = Field(..., ge=0, lt=20, description="Y coordinate (0-19)")
    d: int = Field(..., ge=0, le=8, description="Direction (0=N, 2=E, 4=S, 6=W, 8=SKIP)")
    id: int = Field(..., gt=0, description="Obstacle ID (positive integer)")


class PathfindingRequest(BaseModel):
    """Request body for the /path endpoint."""
    obstacles: List[ObstacleRequest] = Field(
        ...,
        min_length=1,
        max_length=8,
        description="List of obstacles (1-8)"
    )
    robot_x: int = Field(1, ge=0, lt=20, description="Robot starting X coordinate")
    robot_y: int = Field(1, ge=0, lt=20, description="Robot starting Y coordinate")
    robot_dir: int = Field(0, ge=0, le=6, description="Robot starting direction (0=N, 2=E, 4=S, 6=W)")

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "obstacles": [
                    {"x": 5, "y": 10, "d": 0, "id": 1},
                    {"x": 15, "y": 5, "d": 4, "id": 2}
                ],
                "robot_x": 1,
                "robot_y": 1,
                "robot_dir": 0
            }]
        }
    }
