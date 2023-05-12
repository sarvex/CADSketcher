import logging
from enum import Enum

from bpy.types import Operator, Context
from bpy.props import FloatProperty
from mathutils import Vector
from mathutils.geometry import (
    intersect_line_line_2d,
    intersect_line_sphere_2d,
    intersect_sphere_sphere_2d,
)

from ..model.types import SlvsPoint2D
from ..utilities.view import refresh
from ..solver import solve_system
from ..utilities.data_handling import to_list, is_entity_referenced
from ..declarations import Operators
from ..stateful_operator.utilities.register import register_stateops_factory
from ..stateful_operator.state import state_from_args
from .base_2d import Operator2d


logger = logging.getLogger(__name__)


class ElementTypes(str, Enum):
    Line = "LINE"
    Sphere = "Sphere"


def _get_intersection_func(type_a, type_b):
    if all(t == ElementTypes.Line for t in (type_a, type_b)):
        return intersect_line_line_2d
    if all(t == ElementTypes.Sphere for t in (type_a, type_b)):
        return intersect_sphere_sphere_2d
    return intersect_line_sphere_2d


def _order_intersection_args(arg1, arg2):
    if arg1[0] == ElementTypes.Sphere and arg1[0] == ElementTypes.Line:
        return arg2, arg1
    return arg1, arg2


def _get_offset_line(line, offset):
    normal = line.normal()
    offset_vec = normal * offset
    return (line.p1.co + offset_vec, line.p2.co + offset_vec)


def _get_offset_sphere(arc, offset):
    """Return sphere_co and sphere_radius of offset sphere"""
    return arc.ct.co, arc.radius + offset


def _get_offset_elements(entity, offset):
    t = ElementTypes.Line if entity.type == "SlvsLine2D" else ElementTypes.Sphere
    func = _get_offset_sphere if t == ElementTypes.Sphere else _get_offset_line
    return (
        (t, func(entity, offset)),
        (t, func(entity, -offset)),
    )


def _get_intersections(*element_list):
    """Find all intersections between all combinations of elements, (type, element)"""
    intersections = []
    lenght = len(element_list)

    for i, elem_a in enumerate(element_list):
        if i + 1 == lenght:
            break
        for elem_b in element_list[i + 1 :]:
            a, b = _order_intersection_args(elem_a, elem_b)
            func = _get_intersection_func(a[0], b[0])
            retval = to_list(func(*a[1], *b[1]))

            intersections.extend(intr for intr in retval if intr)
    return intersections


class View3D_OT_slvs_bevel(Operator, Operator2d):
    """Add a tangential arc between the two segments of a selected point"""

    bl_idname = Operators.Bevel
    bl_label = "Sketch Bevel"
    bl_options = {"REGISTER", "UNDO"}

    radius: FloatProperty(name="Radius")

    states = (
        state_from_args(
            "Point",
            description="Point to bevel",
            pointer="p1",
            types=(SlvsPoint2D,),
        ),
        state_from_args(
            "Radius",
            description="Radius of the bevel",
            property="radius",
            interactive=True,
        ),
    )

    def main(self, context):
        sketch = self.sketch
        sse = context.scene.sketcher.entities

        point = self.p1
        radius = self.radius

        connected = [
            e for e in (*sse.lines2D, *sse.arcs) if point in e.connection_points()
        ]
        if len(connected) != 2:
            self.report({"WARNING"}, "Point should have two connected segments")
            return False

        l1, l2 = connected
        self.connected = connected

        # If more than 1 intersection point, then sort them so we prioritise
        # the closest ones to the selected point.
        #   (Can happen with intersecting arcs)
        intersections = sorted(
            _get_intersections(
                *_get_offset_elements(l1, radius),
                *_get_offset_elements(l2, radius),
            ),
            key=lambda i: (i - self.p1.co).length,
        )

        coords = None
        for intersection in intersections:
            if hasattr(l1, "is_inside") and not l1.is_inside(intersection):
                continue
            if hasattr(l2, "is_inside") and not l2.is_inside(intersection):
                continue
            coords = intersection
            break

        if not coords:
            return False

        self.ct = sse.add_point_2d(coords, sketch)

        # Get tangent points
        p1_co, p2_co = l1.project_point(coords), l2.project_point(coords)

        if any(co is None for co in (p1_co, p2_co)):
            return False

        self.points = (
            sse.add_point_2d(p1_co, sketch),
            sse.add_point_2d(p2_co, sketch),
        )

        # Get direction of arc
        connection_angle = l1.connection_angle(l2, connection_point=self.p1)
        invert = connection_angle < 0

        # Add Arc
        self.arc = sse.add_arc(sketch.wp.nm, self.ct, *self.points, sketch)
        self.arc.invert_direction = invert

        refresh(context)
        return True

    def fini(self, context, succeede):
        if not succeede:
            return

        sketch = self.sketch

        # Replace endpoints of existing segments
        point = self.p1
        p1, p2 = self.points

        seg1, seg2 = self.connected
        seg1.replace_point(point, p1)
        seg2.replace_point(point, p2)

        context.view_layer.update()

        # Add tangent constraints
        ssc = context.scene.sketcher.constraints
        ssc.add_tangent(self.arc, seg1, sketch)
        ssc.add_tangent(self.arc, seg2, sketch)

        # Remove original point if not referenced
        if not is_entity_referenced(point, context):
            context.scene.sketcher.entities.remove(point.slvs_index)

        refresh(context)
        solve_system(context)


register, unregister = register_stateops_factory((View3D_OT_slvs_bevel,))
