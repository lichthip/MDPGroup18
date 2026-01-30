from typing import Union
import heapq
import math
import numpy as np
from python_tsp.heuristics import solve_tsp_lin_kernighan

from src.entities.entity import CellState, Obstacle, Grid
from src.entities.robot import Robot
from src.tools.consts import (
    TURN_FACTOR,
    ITERATIONS,
    SAFE_COST,
    TURN_DISPLACEMENT,
    REVERSE_FACTOR,
    PADDING,
    ARENA_WIDTH,
    ARENA_HEIGHT,
)
from src.tools.movement import (
    Direction,
    MOVE_DIRECTION,
    Motion
)


class MazeSolver:
    """
    A class that finds the shortest path given a grid, robot and obstacles
    
    Uses A* search for pathfinding between positions and TSP solving for
    optimal obstacle visitation order
    """

    def __init__(
            self,
            size_x: int = ARENA_WIDTH,
            size_y: int = ARENA_HEIGHT,
            robot: Union[Robot, None] = None,
            robot_x: int = 1,
            robot_y: int = 1,
            robot_direction: Direction = Direction.NORTH,
    ) -> None:
        """
        Args:
            size_x: size of the grid in x direction. Default is 20
            size_y: size of the grid in y direction. Default is 20
            robot: A robot object that contains the robot's path
            robot_x: x coordinate of the robot. Default is 1
            robot_y: y coordinate of the robot. Default is 1
            robot_direction: direction the robot is facing. Default is NORTH
        """
        self.neighbor_cache = {}  # Store precomputed neighbors
        self.grid = Grid(size_x, size_y)

        self.robot = robot if robot else Robot(
            robot_x, robot_y, robot_direction)

        self.path_table = dict()
        self.cost_table = dict()
        self.motion_table = dict()

    def add_obstacle(
            self, x: int, y: int, direction: Direction, obstacle_id: int
    ) -> None:
        """
        Add an obstacle to the grid.

        Args:
            x: x coordinate of the obstacle
            y: y coordinate of the obstacle
            direction: direction that the image on the obstacle is facing
            obstacle_id: id of the obstacle
        """
        self.grid.add_obstacle(Obstacle(x, y, direction, obstacle_id))

    def clear_obstacles(self) -> None:
        """Removes all obstacles from the grid."""
        self.grid.reset_obstacles()

    def get_optimal_path(self) -> tuple[list[CellState], float]:
        """
        Get the optimal path between all possible view states for all obstacles
        using A* search and solving TSP problem.

        Returns: 
            tuple[list[CellState], float]: optimal path as list of CellStates, and total cost
        """
        min_dist = 1e9
        optimal_path = []

        # get all grid positions that can view the obstacle images
        views = self.grid.get_view_obstacle_positions()
        num_views = len(views)

        for bin_pos in self._get_visit_options(num_views):
            visit_states = [self.robot.get_start_state()]
            cur_view_positions = []

            for i in range(num_views):
                # if the i-th bit is 1, then the robot will visit the view position at obstacle i
                if bin_pos[i] == "1":
                    cur_view_positions.append(views[i])
                    visit_states.extend(views[i])

            # generate path to all other visit states using A* search
            self._generate_paths(visit_states)

            # generate all possible combinations of the view positions
            combinations = MazeSolver._generate_combinations(
                cur_view_positions, 0, [], [], ITERATIONS
            )

            # iterate over all the combinations and find the optimal path
            for combination in combinations:
                visited = [0]

                current_idx = 1  # idx 0 of visit_states: robot start state
                cost = 0

                # iterate over the views for each obstacle and calculate the cost
                for idx, view_pos in enumerate(cur_view_positions):
                    visited.append(current_idx + combination[idx])
                    cost += view_pos[combination[idx]].penalty
                    current_idx += len(view_pos)

                # initialize the cost matrix to travel between each obstacle
                cost_matrix = np.zeros((len(visited), len(visited)))

                for start_idx in range(len(visited) - 1):
                    for end_idx in range(start_idx + 1, len(visited)):
                        start_state = visit_states[visited[start_idx]]
                        end_state = visit_states[visited[end_idx]]

                        if (start_state, end_state) in self.cost_table:
                            cost_matrix[start_idx, end_idx] = self.cost_table[
                                (start_state, end_state)
                            ]
                        else:
                            cost_matrix[start_idx, end_idx] = 1e9

                        cost_matrix[end_idx, start_idx] = cost_matrix[
                            start_idx, end_idx
                        ]

                cost_matrix[:, 0] = 0

                # find Hamiltonian path with least cost using Lin-Kernighan
                permutation, distance = solve_tsp_lin_kernighan(cost_matrix)

                if distance + cost >= min_dist:
                    continue

                min_dist = distance + cost

                # update the optimal path
                optimal_path = [visit_states[0]]
                for idx in range(len(permutation) - 1):
                    from_state = visit_states[visited[permutation[idx]]]
                    to_state = visit_states[visited[permutation[idx + 1]]]

                    current_path = self.path_table[(from_state, to_state)]

                    for idx2 in range(1, len(current_path)):
                        optimal_path.append(
                            CellState(
                                current_path[idx2][0],
                                current_path[idx2][1],
                                current_path[idx2][2],
                            )
                        )

                    # check position of to_state wrt to obstacle for screenshot
                    obs = self.grid.find_obstacle_by_id(to_state.screenshot_id)
                    if obs:
                        pos = MazeSolver._get_capture_relative_position(
                            optimal_path[-1], obs
                        )
                        formatted = f"{to_state.screenshot_id}_{pos}"
                        optimal_path[-1].set_screenshot(formatted)
                    else:
                        raise ValueError(
                            f"Obstacle with id {to_state.screenshot_id} not found"
                        )

            # if the optimal path has been found, break the view positions loop
            if optimal_path:
                break

        return optimal_path, min_dist

    def _generate_paths(self, states: list[CellState]) -> None:
        """Generate and store the path between all combinations of all view states."""
        for i in range(len(states) - 1):
            for j in range(i + 1, len(states)):
                self._astar_search(states[i], states[j])

    def _astar_search(self, start: CellState, end: CellState) -> None:
        """
        A* search algorithm to find the shortest path between two states.
        Each state is defined by x, y, and direction.

        Heuristic: distance f = g + h
        g: Actual distance from the start state to the current state
        h: Estimated distance from the current state to the end state
        """
        if (start, end) in self.path_table:
            return

        g_dist = {(start.x, start.y, start.direction): 0}

        visited = set()
        parent_dict = {}

        # the heap is a list of tuples (h, x, y, direction) where h is the estimated distance from the current state to the end state
        heap = [(self._estimate_distance(start, end),
                 start.x, start.y, start.direction)]

        while heap:
            _, x, y, direction = heapq.heappop(heap)

            if (x, y, direction) in visited:
                continue

            if end.is_eq(x, y, direction):
                self._record_path(start, end, parent_dict,
                                  g_dist[(x, y, direction)])
                return

            visited.add((x, y, direction))
            dist = g_dist[(x, y, direction)]

            for (
                    new_x,
                    new_y,
                    new_direction,
                    safe_cost,
                    motion,
            ) in self._get_neighboring_states(x, y, direction):

                if (new_x, new_y, new_direction) in visited:
                    continue

                if (
                        x, y, direction, new_x, new_y, new_direction,
                ) not in self.motion_table and (
                        new_x, new_y, new_direction, x, y, direction,
                ) not in self.motion_table:
                    self.motion_table[
                        (x, y, direction, new_x, new_y, new_direction)
                    ] = motion

                turn_cost = TURN_FACTOR * Direction.turn_cost(
                    direction, new_direction
                )
                reverse_cost = REVERSE_FACTOR * motion.reverse_cost()

                motion_cost = turn_cost + reverse_cost + safe_cost

                if end.is_eq(new_x, new_y, new_direction):
                    screenshot_cost = end.penalty
                else:
                    screenshot_cost = 0

                total_cost = (
                    dist
                    + motion_cost
                    + screenshot_cost
                    + self._estimate_distance(
                        CellState(new_x, new_y, new_direction), end
                    )
                )

                if (new_x, new_y, new_direction) not in g_dist or g_dist[
                    (new_x, new_y, new_direction)
                ] > dist + motion_cost + screenshot_cost:
                    g_dist[(new_x, new_y, new_direction)] = dist + \
                        motion_cost + screenshot_cost

                    heapq.heappush(
                        heap, (total_cost, new_x, new_y, new_direction))

                    parent_dict[(new_x, new_y, new_direction)] = (
                        x, y, direction)

    def _get_neighboring_states(
            self, x: int, y: int, direction: Direction
    ) -> list[tuple[int, int, Direction, int, Motion]]:
        """
        Returns list of possible valid cell states the robot can reach from its current position.
        Neighbors have the following format: (newX, newY, movement direction, safe cost, motion)
        """
        if (x, y, direction) in self.neighbor_cache:
            return self.neighbor_cache[(x, y, direction)]
        neighbors = []

        for dx, dy, md in MOVE_DIRECTION:
            if md == direction:  # straight-line motion
                # FORWARD
                if self.grid.reachable(x + dx, y + dy):
                    safe_cost = self._calculate_safe_cost(x + dx, y + dy)
                    motion = Motion.FORWARD
                    neighbors.append((x + dx, y + dy, md, safe_cost, motion))

                # REVERSE
                if self.grid.reachable(x - dx, y - dy):
                    safe_cost = self._calculate_safe_cost(x - dx, y - dy)
                    motion = Motion.REVERSE
                    neighbors.append((x - dx, y - dy, md, safe_cost, motion))

            else:  # turns
                delta_big = TURN_DISPLACEMENT[0]
                delta_small = TURN_DISPLACEMENT[1]

                # all 8 turn combinations
                turn_configs = self._get_turn_configs(
                    direction, md, delta_big, delta_small, x, y
                )
                
                for new_x, new_y, motion in turn_configs:
                    if self.grid.turn_reachable(x, y, new_x, new_y, direction):
                        safe_cost = self._calculate_safe_cost(new_x, new_y)
                        neighbors.append((new_x, new_y, md, safe_cost, motion))

        self.neighbor_cache[(x, y, direction)] = neighbors
        return neighbors

    def _get_turn_configs(
            self, direction: Direction, md: Direction,
            delta_big: int, delta_small: int, x: int, y: int
    ) -> list[tuple[int, int, Motion]]:
        """Get all valid turn configurations for a direction change."""
        configs = []
        
        # north -> east
        if direction == Direction.NORTH and md == Direction.EAST:
            configs.append((x + delta_big, y + delta_small, Motion.FORWARD_RIGHT_TURN))
            configs.append((x - delta_small, y - delta_big, Motion.REVERSE_LEFT_TURN))
        
        # east -> north
        elif direction == Direction.EAST and md == Direction.NORTH:
            configs.append((x + delta_small, y + delta_big, Motion.FORWARD_LEFT_TURN))
            configs.append((x - delta_big, y - delta_small, Motion.REVERSE_RIGHT_TURN))
        
        # east -> south
        elif direction == Direction.EAST and md == Direction.SOUTH:
            configs.append((x + delta_small, y - delta_big, Motion.FORWARD_RIGHT_TURN))
            configs.append((x - delta_big, y + delta_small, Motion.REVERSE_LEFT_TURN))
        
        # south -> east
        elif direction == Direction.SOUTH and md == Direction.EAST:
            configs.append((x + delta_big, y - delta_small, Motion.FORWARD_LEFT_TURN))
            configs.append((x - delta_small, y + delta_big, Motion.REVERSE_RIGHT_TURN))
        
        # south -> west
        elif direction == Direction.SOUTH and md == Direction.WEST:
            configs.append((x - delta_big, y - delta_small, Motion.FORWARD_RIGHT_TURN))
            configs.append((x + delta_small, y + delta_big, Motion.REVERSE_LEFT_TURN))
        
        # west -> south
        elif direction == Direction.WEST and md == Direction.SOUTH:
            configs.append((x - delta_small, y - delta_big, Motion.FORWARD_LEFT_TURN))
            configs.append((x + delta_big, y + delta_small, Motion.REVERSE_RIGHT_TURN))
        
        # west -> north
        elif direction == Direction.WEST and md == Direction.NORTH:
            configs.append((x - delta_small, y + delta_big, Motion.FORWARD_RIGHT_TURN))
            configs.append((x + delta_big, y - delta_small, Motion.REVERSE_LEFT_TURN))
        
        # north -> west
        elif direction == Direction.NORTH and md == Direction.WEST:
            configs.append((x - delta_big, y + delta_small, Motion.FORWARD_LEFT_TURN))
            configs.append((x + delta_small, y - delta_big, Motion.REVERSE_RIGHT_TURN))
        
        return configs

    def _calculate_safe_cost(self, new_x: int, new_y: int) -> int:
        """
        Calculates the safe cost of moving to a new position,
        considering obstacles that the robot might touch.
        """
        for obj in self.grid.obstacles:
            if abs(obj.x - new_x) <= PADDING and abs(obj.y - new_y) <= PADDING:
                return SAFE_COST
            if abs(obj.y - new_y) <= PADDING and abs(obj.x - new_x) <= PADDING:
                return SAFE_COST
        return 0

    def _record_path(
            self, start: CellState, end: CellState,
            parent: dict[tuple[int, int, Direction], tuple[int, int, Direction]],
            cost: int
    ) -> None:
        """Record the path between two states. Called during A* search."""
        self.cost_table[(start, end)] = cost
        self.cost_table[(end, start)] = cost

        path = []
        parent_pointer = (end.x, end.y, end.direction)
        while parent_pointer in parent:
            path.append(parent_pointer)
            parent_pointer = parent[parent_pointer]
        path.append(parent_pointer)

        self.path_table[(start, end)] = path[::-1]
        self.path_table[(end, start)] = path

    @staticmethod
    def _estimate_distance(
            start: CellState, end: CellState, level: int = 0,
    ) -> int:
        """
        Estimate the distance between two states.
        level 0: Manhattan distance
        level 1: Euclidean distance
        """
        horizontal_distance = start.x - end.x
        vertical_distance = start.y - end.y

        if level == 1:
            return math.sqrt(horizontal_distance ** 2 + vertical_distance ** 2)

        return abs(horizontal_distance) + abs(vertical_distance)

    @staticmethod
    def _get_visit_options(n: int) -> list[str]:
        """Generate all possible visit options for n-digit binary numbers."""
        max_len = bin(2 ** n - 1).count("1")
        strings = [bin(i)[2:].zfill(max_len) for i in range(2 ** n)]
        strings.sort(key=lambda x: x.count("1"), reverse=True)
        return strings

    @staticmethod
    def _generate_combinations(
            view_positions: list[list[CellState]],
            index: int,
            current: list[int],
            result: list[list[int]],
            num_iters: int,
    ) -> list[list[int]]:
        """
        Generate all possible combinations of the view positions,
        where one view state is selected for each obstacle.
        """
        if index == len(view_positions):
            result.append(current.copy())
            return result

        if num_iters == 0:
            return result

        num_iters -= 1

        for i in range(len(view_positions[index])):
            current.append(i)
            result = MazeSolver._generate_combinations(
                view_positions, index + 1, current, result, num_iters
            )
            current.pop()

        return result

    @staticmethod
    def _get_capture_relative_position(
        cell_state: CellState, obstacle: Obstacle
    ) -> str:
        """
        Determines the relative position of the obstacle (L, R, or C)
        with respect to the robot's orientation.
        """
        x, y, direction = cell_state.x, cell_state.y, cell_state.direction
        x_obs, y_obs = obstacle.x, obstacle.y

        if direction == Direction.NORTH:
            if x_obs == x and y_obs > y:
                return "C"
            elif x_obs < x:
                return "L"
            else:
                return "R"
        elif direction == Direction.SOUTH:
            if x_obs == x and y_obs < y:
                return "C"
            elif x_obs < x:
                return "R"
            else:
                return "L"
        elif direction == Direction.EAST:
            if y_obs == y and x_obs > x:
                return "C"
            elif y_obs < y:
                return "R"
            else:
                return "L"
        elif direction == Direction.WEST:
            if y_obs == y and x_obs < x:
                return "C"
            elif y_obs < y:
                return "L"
            else:
                return "R"
        else:
            raise ValueError(
                f"Invalid direction {direction}. This should never happen."
            )

    def optimal_path_to_motion_path(
            self, optimal_path: list[CellState]
    ) -> tuple[list[Motion], list[str], list[Obstacle]]:
        """Convert the optimal path to a list of motions that the robot needs to take."""
        motion_path = []
        obstacle_id_with_signals = []
        scanned_obstacles = []
        
        for i in range(len(optimal_path) - 1):
            from_state = optimal_path[i]
            to_state = optimal_path[i + 1]
            x, y, d = from_state.x, from_state.y, from_state.direction
            x_new, y_new, d_new = to_state.x, to_state.y, to_state.direction

            if (x_new, y_new, d_new, x, y, d) in self.motion_table:
                motion = self.motion_table[
                    (x_new, y_new, d_new, x, y, d)
                ].opposite_motion()
            elif (x, y, d, x_new, y_new, d_new) in self.motion_table:
                motion = self.motion_table[(x, y, d, x_new, y_new, d_new)]
            else:
                raise ValueError(
                    f"Invalid path from {from_state} to {to_state}. This should never happen."
                )

            motion_path.append(motion)

            if to_state.screenshot_id is not None:
                motion_path.append(Motion.CAPTURE)
                obstacle_id_with_signals.append(to_state.screenshot_id)
                obstacle_id = int(str(to_state.screenshot_id).split("_")[0])
                scanned_obstacles.append(
                    self.grid.find_obstacle_by_id(obstacle_id)
                )

        return motion_path, obstacle_id_with_signals, scanned_obstacles
