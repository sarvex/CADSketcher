import logging
import math
from typing import Type, Union, Tuple

import bpy
from bpy.types import PropertyGroup
from bpy.props import CollectionProperty
from bpy.utils import register_classes_factory
from mathutils import Vector, Euler

from .. import global_data
from ..utilities.constants import QUARTER_TURN
from ..utilities.index import breakdown_index, assemble_index

from .base_entity import SlvsGenericEntity
from .utilities import slvs_entity_pointer, update_pointers
from .point_3d import SlvsPoint3D
from .line_3d import SlvsLine3D
from .normal_3d import SlvsNormal3D
from .workplane import SlvsWorkplane
from .sketch import SlvsSketch
from .point_2d import SlvsPoint2D
from .line_2d import SlvsLine2D
from .normal_2d import SlvsNormal2D
from .arc import SlvsArc
from .circle import SlvsCircle

logger = logging.getLogger(__name__)


class SlvsEntities(PropertyGroup):
    """Holds all Solvespace Entities"""

    # NOTE: currently limited to 16 items!
    # See _set_index to see how their index is handled
    entities = (
        SlvsPoint3D,
        SlvsLine3D,
        SlvsNormal3D,
        SlvsWorkplane,
        SlvsSketch,
        SlvsPoint2D,
        SlvsLine2D,
        SlvsNormal2D,
        SlvsArc,
        SlvsCircle,
    )

    _entity_collections = (
        "points3D",
        "lines3D",
        "normals3D",
        "workplanes",
        "sketches",
        "points2D",
        "lines2D",
        "normals2D",
        "arcs",
        "circles",
    )

    # __annotations__ = {
    #   list_name : CollectionProperty(type=entity_cls) for entity_cls, list_name in zip(entities, _entity_collections)
    # }

    @classmethod
    def _type_index(cls, entity: SlvsGenericEntity) -> int:
        return cls.entities.index(type(entity))

    def _set_index(self, entity: SlvsGenericEntity):
        """Create an index for the entity and assign it.
        Index breakdown

        | entity type index |  entity object index  |
        |:-----------------:|:---------------------:|
        |      4 bits       |       20 bits         |
        |            total: 3 Bytes                 |
        """
        type_index = self._type_index(entity)
        sub_list = getattr(self, self._entity_collections[type_index])

        local_index = len(sub_list) - 1
        # TODO: handle this case better
        assert local_index < math.pow(2, 20)
        entity.slvs_index = assemble_index(type_index, local_index)

    @staticmethod
    def _breakdown_index(index: int):
        return breakdown_index(index)

    @classmethod
    def recalc_type_index(cls, entity):
        _, local_index = cls._breakdown_index(entity.slvs_index)
        type_index = cls._type_index(entity)
        entity.slvs_index = type_index << 20 | local_index

    def type_from_index(self, index: int) -> Type[SlvsGenericEntity]:
        if index < 0:
            return None

        type_index, _ = self._breakdown_index(index)

        return None if type_index >= len(self.entities) else self.entities[type_index]

    def collection_name_from_index(self, index: int):
        if index < 0:
            return

        type_index, _ = self._breakdown_index(index)
        return self._entity_collections[type_index]

    def _get_list_and_index(self, index: int):
        type_index, local_index = self._breakdown_index(index)
        if type_index < 0 or type_index >= len(self._entity_collections):
            return None, local_index
        return getattr(self, self._entity_collections[type_index]), local_index

    def get(self, index: int) -> SlvsGenericEntity:
        """Get entity by index

        Arguments:
            index: The global index of the entity.

        Returns:
            SlvsGenericEntity: Entity with the given global index or None if not found.
        """
        if index == -1:
            return None
        sub_list, i = self._get_list_and_index(index)
        return None if not sub_list or i >= len(sub_list) else sub_list[i]

    def remove(self, index: int):
        """Remove entity by index

        Arguments:
            index: The global index of the entity.
        """
        assert isinstance(index, int)

        if self.get(index).origin:
            return

        entity_list, i = self._get_list_and_index(index)
        entity_list.remove(i)

        # Put last item to removed index and update all pointers to it
        last_index = len(entity_list) - 1

        if last_index < 0:
            return
        if i > last_index:
            return

        if i != last_index:  # second last item was deleted
            entity_list.move(last_index, i)

        new_item = entity_list[i]
        update_pointers(bpy.context.scene, new_item.slvs_index, index)
        new_item.slvs_index = index

    def add_point_3d(
        self, co: Union[Tuple[float, float, float], Vector]
    ) -> SlvsPoint3D:
        """Add a point in 3d space.

        Arguments:
            co: Location of the point in 3d space.

        Returns:
            SlvsPoint3D: The created point.
        """
        if not hasattr(co, "__len__") or len(co) != 3:
            raise TypeError("Argument co must be of length 3")

        p = self.points3D.add()
        p.location = co
        self._set_index(p)
        return p

    def add_line_3d(self, p1: SlvsPoint3D, p2: SlvsPoint3D) -> SlvsLine3D:
        """Add a line in 3d space.

        Arguments:
            p1: Line's startpoint.
            p2: Line's endpoint.

        Returns:
            SlvsLine3D: The created line.
        """
        line = self.lines3D.add()
        line.p1 = p1
        line.p2 = p2
        self._set_index(line)
        return line

    def add_normal_3d(self, quat: Tuple[float, float, float, float]) -> SlvsNormal3D:
        """Add a normal in 3d space.

        Arguments:
            quat: Quaternion which describes the orientation.

        Returns:
            SlvsNormal3D: The created normal.
        """
        nm = self.normals3D.add()
        nm.orientation = quat
        self._set_index(nm)
        return nm

    def add_workplane(self, p1: SlvsPoint3D, nm: SlvsGenericEntity) -> SlvsWorkplane:
        """Add a workplane.

        Arguments:
            p1: Workplane's originpoint.
            nm: Workplane's normal.

        Returns:
            SlvsWorkplane: The created workplane.
        """
        wp = self.workplanes.add()
        wp.p1 = p1
        wp.nm = nm
        self._set_index(wp)
        return wp

    def add_sketch(self, wp: SlvsWorkplane) -> SlvsSketch:
        """Add a Sketch.

        Arguments:
            wp: Sketch's workplane.

        Returns:
            SlvsSketch: The created sketch.
        """
        sketch = self.sketches.add()
        sketch.wp = wp
        self._set_index(sketch)
        _, i = self._breakdown_index(sketch.slvs_index)
        sketch.name = "Sketch"
        return sketch

    def add_point_2d(self, co: Tuple[float, float], sketch: SlvsSketch) -> SlvsPoint2D:
        """Add a point in 2d space.

        Arguments:
            co: Coordinates of the point on the workplane.
            sketch: The sketch this point belongs to.

        Returns:
            SlvsPoint2D: The created point.
        """
        p = self.points2D.add()
        p.co = co
        p.sketch = sketch
        self._set_index(p)
        return p

    def add_line_2d(
        self, p1: SlvsPoint2D, p2: SlvsPoint2D, sketch: SlvsSketch
    ) -> SlvsLine2D:
        """Add a line in 2d space.

        Arguments:
            p1: Line's startpoint.
            p2: Line's endpoint.
            sketch: The sketch this line belongs to.

        Returns:
            SlvsLine2D: The created line.
        """
        line = self.lines2D.add()
        line.p1 = p1
        line.p2 = p2
        line.sketch = sketch
        self._set_index(line)
        return line

    def add_normal_2d(self, sketch: SlvsSketch) -> SlvsNormal2D:
        """Add a normal in 2d space.

        Arguments:
            sketch: The sketch this normal belongs to.

        Returns:
            SlvsNormal2D: The created normal.
        """
        nm = self.normals2D.add()
        nm.sketch = sketch
        self._set_index(nm)
        return nm

    def add_arc(
        self,
        nm: SlvsNormal2D,
        ct: SlvsPoint2D,
        p1: SlvsPoint2D,
        p2: SlvsPoint2D,
        sketch: SlvsSketch,
    ) -> SlvsArc:
        """Add an arc in 2d space.

        Arguments:
            ct: Arc's centerpoint.
            p1: Arc's startpoint.
            p2: Arc's endpoint.
            sketch: The sketch this arc belongs to.
            nm: Arc's normal.

        Returns:
            SlvsArc: The created arc.
        """
        arc = self.arcs.add()
        arc.nm = nm
        arc.ct = ct
        arc.p1 = p1
        arc.p2 = p2
        arc.sketch = sketch
        self._set_index(arc)
        return arc

    def add_circle(
        self, nm: SlvsNormal2D, ct: SlvsPoint2D, radius: float, sketch: SlvsSketch
    ) -> SlvsCircle:
        """Add a circle in 2d space.

        Arguments:
            ct: Circle's centerpoint.
            radius: Circle's radius.
            sketch: The sketch this circle belongs to.
            nm: Circle's normal.

        Returns:
            SlvsCircle: The created circle.
        """
        c = self.circles.add()
        c.nm = nm
        c.ct = ct
        c.radius = radius
        c.sketch = sketch
        self._set_index(c)
        return c

    @property
    def all(self):
        for coll_name in self._entity_collections:
            yield from getattr(self, coll_name)

    @property
    def selected(self):
        """Return all selected entities, might include inactive entities"""
        context = bpy.context
        items = []
        for index in global_data.selected:
            entity = self.get(index)
            items.append(entity)
        return [e for e in items if e.is_selectable(context)]

    @property
    def selected_all(self):
        """Return all selected entities, might include invisible entities"""
        context = bpy.context
        items = []
        for index in global_data.selected:
            entity = self.get(index)
            items.append(entity)
        return [e for e in items if e.selected]

    @property
    def selected_active(self):
        """Returns all selected and active entities"""
        context = bpy.context
        active_sketch = context.scene.sketcher.active_sketch
        return [e for e in self.selected if e.is_active(active_sketch)]

    def ensure_origin_elements(self, context):
        def set_origin_props(e):
            e.fixed = True
            e.origin = True

        sse = context.scene.sketcher.entities
        # origin
        if not self.origin:
            p = sse.add_point_3d((0.0, 0.0, 0.0))
            set_origin_props(p)
            self.origin = p

        # axis
        pi_2 = QUARTER_TURN
        for name, angles in zip(
            ("origin_axis_X", "origin_axis_Y", "origin_axis_Z"),
            (Euler((pi_2, 0.0, pi_2)), Euler((pi_2, 0.0, 0.0)), Euler()),
        ):
            if getattr(self, name):
                continue
            nm = sse.add_normal_3d(Euler(angles).to_quaternion())
            set_origin_props(nm)
            setattr(self, name, nm)

        # workplanes
        for nm_name, wp_name in (
            ("origin_axis_X", "origin_plane_YZ"),
            ("origin_axis_Y", "origin_plane_XZ"),
            ("origin_axis_Z", "origin_plane_XY"),
        ):
            if getattr(self, wp_name):
                continue
            wp = sse.add_workplane(self.origin, getattr(self, nm_name))
            set_origin_props(wp)
            setattr(self, wp_name, wp)

    def collection_offsets(self):
        return {
            i: len(getattr(self, key))
            for i, key in enumerate(self._entity_collections)
        }


if not hasattr(SlvsEntities, "__annotations__"):
    SlvsEntities.__annotations__ = {}
for entity_cls, list_name in zip(
    SlvsEntities.entities, SlvsEntities._entity_collections
):
    SlvsEntities.__annotations__[list_name] = CollectionProperty(type=entity_cls)


slvs_entity_pointer(SlvsEntities, "origin")
slvs_entity_pointer(SlvsEntities, "origin_axis_X")
slvs_entity_pointer(SlvsEntities, "origin_axis_Y")
slvs_entity_pointer(SlvsEntities, "origin_axis_Z")
slvs_entity_pointer(SlvsEntities, "origin_plane_XY")
slvs_entity_pointer(SlvsEntities, "origin_plane_XZ")
slvs_entity_pointer(SlvsEntities, "origin_plane_YZ")


register, unregister = register_classes_factory((SlvsEntities,))
