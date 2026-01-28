"""Command generator for STM32 motor commands."""

from src.tools.movement import Motion
from src.entities.entity import Obstacle
from src.tools.consts import OFFSET, OBSTACLE_SIZE, W_COMMAND_FLAG


class CommandGenerator:
    """
    Generate commands in format requested by STM32.
    
    Command format: "{flag}{speed}|{angle}|{val}\\n"
    
    <speed>: 1-3 chars, specify speed to drive (0-100)
    <angle>: 1+ chars in degrees, steering angle (-25 to 25)
             negative = steer left, positive = steer right
    <val>: 1+ chars in cm, distance to drive (0-500)
           For DIST_TARGET with angle != 0: turn angle to complete (0-360)
    
    Examples:
        'T50|0|30'  -> forward at speed 50, straight, 30cm
        't35|0|20'  -> reverse at speed 35, straight, 20cm
    """
    
    SEP = "|"
    END = "\n"
    FIN = 'FIN'
    
    # flags
    FORWARD_DIST_TARGET = "T"   # go forward for a target distance/angle
    FORWARD_DIST_AWAY = "W"    # go forward until within distance from obstacle
    BACKWARD_DIST_TARGET = "t"  # go backward for a target distance/angle
    BACKWARD_DIST_AWAY = "w"   # go backward until distance from obstacle

    # unit distance in cm (1 grid cell = 10cm)
    UNIT_DIST: float = 10

    def __init__(self, straight_speed: int = 50, turn_speed: int = 30) -> None:
        """
        Args:
            straight_speed: Speed for straight-line movement (0-100)
            turn_speed: Speed for turning (0-100)
        """
        self.straight_speed: int = straight_speed
        self.turn_speed: int = turn_speed

    def _generate_command(self, motion: Motion, num_motions: int = 1) -> list[str]:
        """
        Generates movement commands based on motion type.
        
        Tune accordingly to the robot's hardware.
        
        Args:
            motion: Type of motion to execute
            num_motions: Number of repeated motions (for combining straight moves)
        
        Returns:
            list[str]: List of command strings
        """
        if num_motions > 1:
            dist = num_motions * self.UNIT_DIST
        else:
            dist = self.UNIT_DIST

        if motion == Motion.FORWARD:
            return [f"T{self.straight_speed}|{0}|{dist}"]
        
        elif motion == Motion.REVERSE:
            # servo tends to drift left when reversing, re-align every 20cm
            realign_cmds = [f"T{25}|{30}|{0.1}"]
            cmds = []
            
            for _ in range(int(dist) // 20):
                cmds.append(f"t{35}|{0}|{20}")
                cmds.extend(realign_cmds)

            remaining_dist = int(dist) % 20
            if remaining_dist > 0:
                cmds.append(f"t{35}|{0}|{remaining_dist}")
                if remaining_dist >= 5:
                    cmds.extend(realign_cmds)
            return cmds

        # turn commands - tuned for 3-point turns due to hardware limitations
        elif motion == Motion.FORWARD_LEFT_TURN:
            return [
                f"T{30}|{-50}|{46}",
                f"t{25}|{0}|{23}",
                f"T{30}|{-50}|{45.5}",
                f"T{25}|{10}|{0.1}",  # re-align servo
                f"t{25}|{0}|{3}"
            ]
        
        elif motion == Motion.FORWARD_RIGHT_TURN:
            return [
                f"T{30}|{50}|{46}",
                f"t{25}|{0}|{20}",
                f"T{30}|{50}|{45.7}",
                f"t{25}|{0}|{4}",
            ]
        
        elif motion == Motion.REVERSE_LEFT_TURN:
            return [
                f"T{25}|{0}|{3}",
                f"t{30}|{-50}|{46}",
                f"T{25}|{0}|{22}",
                f"t{30}|{-50}|{46.5}",
                f"T{25}|{10}|{0.1}"  # re-align servo
            ]
        
        elif motion == Motion.REVERSE_RIGHT_TURN:
            return [
                f"T{25}|{0}|{6}",
                f"t{30}|{48}|{45.4}",
                f"T{25}|{0}|{14}",
                f"t{30}|{48}|{45.5}"
            ]
        
        else:
            raise ValueError(f"Invalid motion {motion}. This should never happen.")

    def _generate_away_command(self, view_state, obstacle: Obstacle) -> list[str]:
        """Generate commands to calibrate robot position before scanning obstacle."""
        CLEARANCE = 0.3

        unit_dist_from_obstacle = max(
            abs(view_state.x - obstacle.x),
            abs(view_state.y - obstacle.y)
        ) - OFFSET - OBSTACLE_SIZE + CLEARANCE
        dist_away = int(unit_dist_from_obstacle * self.UNIT_DIST)
        
        return [
            f"{self.FORWARD_DIST_AWAY}{self.straight_speed}{self.SEP}{0}{self.SEP}{dist_away}",
            f"{self.BACKWARD_DIST_AWAY}{self.straight_speed}{self.SEP}{0}{self.SEP}{dist_away}"
        ]

    def generate_commands(
            self,
            motions: list[Motion],
            obstacle_id_with_signals: list[str],
            scanned_obstacles: list[Obstacle],
            optimal_path
    ) -> list[str]:
        """
        Generate commands based on the list of motions.
        
        Args:
            motions: List of Motion enums representing the path
            obstacle_id_with_signals: List of obstacle IDs with position signals (e.g., "1_C")
            scanned_obstacles: List of Obstacle objects being scanned
            optimal_path: The optimal path (list of CellStates)
        
        Returns:
            list[str]: List of command strings for STM32
        """
        if not motions:
            return []
        
        view_states = [
            position for position in optimal_path if position.screenshot_id is not None
        ]
        commands: list[str] = []
        prev_motion: Motion = motions[0]
        num_motions: int = 1
        snap_count: int = 0
        
        for motion in motions[1:]:
            # combine consecutive straight motions
            if motion == prev_motion and motion.is_combinable():
                num_motions += 1
            else:
                if prev_motion == Motion.CAPTURE:
                    if (
                        W_COMMAND_FLAG
                        and "C" in obstacle_id_with_signals[snap_count]
                    ):
                        commands.extend(
                            self._generate_away_command(
                                view_states[snap_count], scanned_obstacles[snap_count]
                            )
                        )
                    commands.append(f"SNAP{obstacle_id_with_signals[snap_count]}")
                    snap_count += 1
                    prev_motion = motion
                    continue
                else:
                    cur_cmd = self._generate_command(prev_motion, num_motions)
                commands.extend(cur_cmd)
                num_motions = 1
            prev_motion = motion

        # add the last command
        if prev_motion == Motion.CAPTURE:
            if (
                W_COMMAND_FLAG
                and "C" in obstacle_id_with_signals[snap_count]
            ):
                commands.extend(
                    self._generate_away_command(
                        view_states[snap_count], scanned_obstacles[snap_count]
                    )
                )
            commands.append(f"SNAP{obstacle_id_with_signals[snap_count]}")
        else:
            cur_cmd = self._generate_command(prev_motion, num_motions)
            commands.extend(cur_cmd)

        # add final command
        commands.append(f"{self.FIN}")
        return commands
