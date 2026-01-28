"""tunable constants for the algo

these values can be adjusted to tune robot behavior:
- cost weights affect path selection
- physical params shd match actual robot measurements
"""

# expanded cell for safety margin (in 10cm units)
# higher value = more space around obstacles, harder to find paths
EXPANDED_CELL: int = 1

# arena dimensions (in 10cm units, so 20 = 200cm = 2m)
ARENA_WIDTH: int = 20
ARENA_HEIGHT: int = 20

# obstacle size (in 10cm units)
OBSTACLE_SIZE: int = 1

# number of iterations to run algorithm for finding shortest path
# higher value = more accurate but slower
ITERATIONS: int = 5000

# cost for the chance that the robot touches an obstacle
# higher value = robot stays further from obstacles
SAFE_COST: int = 1000

# cost of taking an image off-center
# higher value = robot prefers center positions for photos
SCREENSHOT_COST: int = 100

# cost for when the robot is too close or too far from the obstacle
DISTANCE_COST: int = 1000

# cost multiplier for turning the robot
# higher value = robot prefers straight paths
TURN_FACTOR: int = 5

# cost multiplier for reversing the robot
# higher value = robot prefers forward motion
REVERSE_FACTOR: int = 0

"""
Turn displacement - how many units the robot moves during a turn.
This must be tuned based on real robot movement.

Example: Motion.FORWARD_LEFT_TURN
.  .   .  .  .
.  .   .  .  .   
X <----┐  .  .  
.  .   |  .  .   
.  .   X  .  .

Index 0: long axis (2 = 20cm)
Index 1: short axis (1 = 10cm)
"""
TURN_DISPLACEMENT: tuple[int, int] = (2, 1)

# offset: how many cells the robot occupies from its center
OFFSET: int = 1

# padding for collision checking (minimum distance from robot to obstacle)
TURN_PADDING: int = (OFFSET + 1) * EXPANDED_CELL
MID_TURN_PADDING: int = (OFFSET + 1) * EXPANDED_CELL
PADDING: int = (OFFSET + 1) * EXPANDED_CELL

# minimum clearance: front of robot at least this many cells from obstacle
MIN_CLEARANCE: int = 1  # 10cm

# use ultrasonic sensor for straight-line motions (0 = disabled, 1 = enabled)
W_COMMAND_FLAG: int = 0
