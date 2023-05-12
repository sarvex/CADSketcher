import sys
from enum import Enum

from mathutils import Vector

registered = False

PYPATH = sys.executable

entities = {}
batches = {}

offscreen = None
redraw_selection_buffer = False

hover = -1
ignore_list = []
selected = []

# Allows to highlight a constraint gizmo,
# Value gets unset in the preselection gizmo
highlight_constraint = None

highlight_entities = []

Z_AXIS = Vector((0, 0, 1))

draw_handle = None

COPY_BUFFER = {}


class WpReq(Enum):
    """Workplane requirement options"""

    OPTIONAL, FREE, NOT_FREE = range(3)


solver_state_items = [
    (
        "OKAY",
        "Okay",
        "Successfully solved sketch.",
        "CHECKMARK",
        0,  # SLVS_RESULT_OKAY
    ),
    (
        "INCONSISTENT",
        "Inconsistent",
        'Cannot solve sketch because of inconsistent constraints, check through the failed constraints and remove the ones that contradict each other.',
        "ERROR",
        1,
    ),
    (
        "DIDNT_CONVERGE",
        "Didnt Converge",
        "Cannot solve sketch, system didn't converge.",
        "ERROR",
        2,  # SLVS_RESULT_DIDNT_CONVERGE
    ),
    (
        "TOO_MANY_UNKNOWNS",
        "Too Many Unknowns",
        "Cannot solve sketch because of too many unknowns.",
        "ERROR",
        3,  # SLVS_RESULT_TOO_MANY_UNKNOWNS
    ),
    (
        "INIT_ERROR",
        "Initialize Error",
        "Solver failed to initialize.",
        "ERROR",
        4,  # SLVS_RESULT_INIT_ERROR
    ),
    (
        "REDUNDANT_OK",
        "Redundant Constraints",
        "Some constraints seem to be redundant, this might cause an error once the constraints are no longer consistent. Check through the marked constraints and only keep what's necessary.",
        "INFO",
        5,
    ),
    (
        "UNKNOWN_FAILURE",
        "Unknown Failure",
        "Cannot solve sketch because of unknown failure.",
        "ERROR",
        6,
    ),
]
