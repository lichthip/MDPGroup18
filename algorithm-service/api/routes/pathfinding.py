import time
import logging
from fastapi import APIRouter, HTTPException

from api.schemas.requests import PathfindingRequest
from api.schemas.responses import PathfindingResponse, PathState
from src.algorithms.algo import MazeSolver
from src.tools.commands import CommandGenerator

router = APIRouter(tags=["Pathfinding"])
logger = logging.getLogger(__name__)


@router.post("/path", response_model=PathfindingResponse)
async def find_path(request: PathfindingRequest):
    """
    Compute optimal path to visit all obstacles.
    
    Given a list of obstacles and robot starting position, this endpoint:
    1. Uses A* search to find shortest paths between positions
    2. Solves TSP to find optimal visitation order
    3. Generates STM32 motor commands
    
    Returns the computed path and commands.
    """
    try:
        maze_solver = MazeSolver(
            size_x=20, size_y=20,
            robot_x=request.robot_x,
            robot_y=request.robot_y,
            robot_direction=request.robot_dir
        )

        for ob in request.obstacles:
            maze_solver.add_obstacle(ob.x, ob.y, ob.d, ob.id)

        start = time.time()
        optimal_path, cost = maze_solver.get_optimal_path()
        runtime = time.time() - start

        logger.info(f"Path found in {runtime:.3f}s, cost={cost}")

        if not optimal_path:
            raise HTTPException(
                status_code=422,
                detail="No valid path found for given obstacles"
            )

        motions, obstacle_ids, scanned = maze_solver.optimal_path_to_motion_path(optimal_path)
        commands = CommandGenerator().generate_commands(
            motions, obstacle_ids, scanned, optimal_path
        )

        path_states = [
            PathState(
                x=state.x,
                y=state.y,
                d=int(state.direction),
                s=state.screenshot_id
            )
            for state in optimal_path
        ]

        return PathfindingResponse(
            path=path_states,
            commands=commands,
            cost=cost,
            runtime=runtime
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error in pathfinding")
        raise HTTPException(status_code=500, detail=str(e))
