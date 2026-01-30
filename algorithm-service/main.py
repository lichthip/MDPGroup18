import time

from src.algorithms.algo import MazeSolver
from src.tools.commands import CommandGenerator
from src.tools.movement import Direction


def main():
    obstacles = [
        {"x": 0, "y": 17, "d": Direction.EAST, "id": 1},
        {"x": 5, "y": 12, "d": Direction.SOUTH, "id": 2},
        {"x": 7, "y": 5, "d": Direction.NORTH, "id": 3},
        {"x": 15, "y": 2, "d": Direction.WEST, "id": 4},
        {"x": 11, "y": 14, "d": Direction.EAST, "id": 5},
    ]

    print("Direct Test")
    print(f"\nObstacles ({len(obstacles)}):")
    for ob in obstacles:
        print(f"  ID {ob['id']}: ({ob['x']}, {ob['y']}) facing {ob['d'].name}")

    # initialize solver
    maze_solver = MazeSolver(
        size_x=20, size_y=20,
        robot_x=1, robot_y=1,
        robot_direction=Direction.NORTH
    )

    # add obstacles
    for ob in obstacles:
        maze_solver.add_obstacle(ob['x'], ob['y'], ob['d'], ob['id'])

    # find optimal path
    start = time.time()
    optimal_path, cost = maze_solver.get_optimal_path()
    runtime = time.time() - start

    print(f"\nPath found")
    print(f"  Time: {runtime:.3f}s")
    print(f"  Cost: {cost:.1f} units")
    print(f"  Path length: {len(optimal_path)} states")

    # generate commands
    motions, obstacle_ids, scanned = maze_solver.optimal_path_to_motion_path(optimal_path)
    commands = CommandGenerator().generate_commands(motions, obstacle_ids, scanned, optimal_path)

    print(f"\nCommands ({len(commands)}):")
    for i, cmd in enumerate(commands):
        print(f"  [{i+1:2d}] {cmd}")

    print("\nTest complete")


if __name__ == "__main__":
    main()
