import logging
import math
from typing import List

import bpy
from bpy.types import PropertyGroup
from gpu_extras.batch import batch_for_shader
from bpy.utils import register_classes_factory
from mathutils import Matrix
from mathutils.geometry import intersect_line_line_2d

from ..solver import Solver
from .base_entity import SlvsGenericEntity
from .base_entity import Entity2D
from .utilities import slvs_entity_pointer, get_connection_point, round_v
from ..utilities.geometry import nearest_point_line_line


logger = logging.getLogger(__name__)


class SlvsLine2D(Entity2D, PropertyGroup):
    """Representation of a line in 2D space. Connects p1 and p2 and lies on the
    sketche's workplane.

    Arguments:
        p1 (SlvsPoint2D): Line's startpoint
        p2 (SlvsPoint2D): Line's endpoint
        sketch (SlvsSketch): The sketch this entity belongs to
    """

    @classmethod
    def is_path(cls):
        return True

    @classmethod
    def is_line(cls):
        return True

    @classmethod
    def is_segment(cls):
        return True

    def dependencies(self) -> List[SlvsGenericEntity]:
        return [self.p1, self.p2, self.sketch]

    def is_dashed(self):
        return self.construction

    def update(self):
        if bpy.app.background:
            return

        p1, p2 = self.p1.location, self.p2.location
        coords = (p1, p2)

        kwargs = {"pos": coords}
        self._batch = batch_for_shader(self._shader, "LINES", kwargs)
        self.is_dirty = False

    def create_slvs_data(self, solvesys, group=Solver.group_fixed):
        handle = solvesys.addLineSegment(self.p1.py_data, self.p2.py_data, group=group)
        self.py_data = handle

    def closest_picking_point(self, origin, view_vector):
        """Returns the point on this entity which is closest to the picking ray"""
        # NOTE: for 2d entities it could be enough precise to simply take the intersection point with the workplane
        p1 = self.p1.location
        d1 = self.p2.location - p1  # normalize?
        return nearest_point_line_line(p1, d1, origin, view_vector)

    def project_point(self, coords):
        """Projects a point onto the line"""
        nm = self.normal
        dir_vec = self.direction_vec()
        p1 = self.p1.co

        local_co = coords - p1
        return local_co.project(dir_vec) + p1

    def placement(self):
        return (self.p1.location + self.p2.location) / 2

    def connection_points(self):
        return [self.p1, self.p2]

    def direction(self, point, is_endpoint=False):
        """Returns the direction of the line, true if inverted"""
        return point == self.p1 if is_endpoint else point == self.p2

    def connection_angle(self, other, **kwargs):
        """Returns the angle at the connection point between the two entities
        or None if they're not connected or not in 2d space.

        `kwargs` key values are propagated to other `get_connection_point` functions
        """

        if self.is_3d() or other.is_3d():
            return None

        if not all(e.is_line() for e in (self, other)):
            return other.connection_angle(self, **kwargs)

        point = get_connection_point(
            self,
            other,
        )
        if not point:
            return None

        dir1 = (
            self.direction_vec()
            if self.direction(point)
            else (self.direction_vec() * (-1))
        )
        dir2 = (
            other.direction_vec()
            if other.direction(point)
            else (other.direction_vec() * (-1))
        )
        return dir1.angle_signed(dir2)

    def to_bezier(
        self, spline, startpoint, endpoint, invert_direction, set_startpoint=False
    ):
        locations = [self.p1.co.to_3d(), self.p2.co.to_3d()]
        if invert_direction:
            locations.reverse()

        if set_startpoint:
            startpoint.co = locations[0]
        endpoint.co = locations[1]

        startpoint.handle_right = locations[0]
        endpoint.handle_left = locations[1]

        return endpoint

    def midpoint(self):
        return (self.p1.co + self.p2.co) / 2

    def direction_vec(self):
        return (self.p2.co - self.p1.co).normalized()

    def normal(self):
        mat_rot = Matrix.Rotation(math.pi / 2, 2, "Z")
        nm = self.direction_vec()
        nm.rotate(mat_rot)
        return nm

    @property
    def length(self):
        return (self.p2.co - self.p1.co).length

    def overlaps_endpoint(self, co):
        precision = 5
        co_rounded = round_v(co, ndigits=precision)
        return any(
            co_rounded == round_v(v, ndigits=precision)
            for v in (self.p1.co, self.p2.co)
        )

    def intersect(self, other):
        # NOTE: There can be multiple intersections when intersecting with one or more curves
        def parse_retval(value):
            if not value:
                return ()
            if self.overlaps_endpoint(value) or other.overlaps_endpoint(value):
                return ()
            return (value,)

        if other.is_line():
            return parse_retval(
                intersect_line_line_2d(self.p1.co, self.p2.co, other.p1.co, other.p2.co)
            )
        else:
            return other.intersect(self)

    def replace(self, context, p1, p2, use_self=False):
        # Replace entity by a similar entity with the connection points p1, and p2
        # This is used for trimming, points are expected to lie somewhere on the existing entity
        if use_self:
            self.p1 = p1
            self.p2 = p2
            return self

        sse = context.scene.sketcher.entities
        sketch = context.scene.sketcher.active_sketch
        line = sse.add_line_2d(
            p1,
            p2,
            sketch,
        )
        line.construction = self.construction
        return line

    def distance_along_segment(self, p1, p2):
        start, end = self.p1.co, self.p2.co
        len_1 = (p1 - end).length
        len_2 = (p2 - start).length

        threshold = 0.0000001
        return (len_1 + len_2) % (self.length + threshold)

    def replace_point(self, old, new):
        for ptr in ("p1", "p2"):
            if old != getattr(self, ptr):
                continue
            setattr(self, ptr, new)
            break


slvs_entity_pointer(SlvsLine2D, "p1")
slvs_entity_pointer(SlvsLine2D, "p2")
slvs_entity_pointer(SlvsLine2D, "sketch")

register, unregister = register_classes_factory((SlvsLine2D,))
