import shutil
import sys
import logging
from os import path

import bpy

from .register import get_path

logger = logging.getLogger(__name__)


def ensure_addon_presets(force_write=False):

    scripts_folder = bpy.utils.user_resource("SCRIPTS")
    presets_dir = path.join(scripts_folder, "presets", "bgs")

    is_existing = bool(path.isdir(presets_dir))
    if force_write or not is_existing:
        bundled_presets = path.join(get_path(), "resources", "presets")

        kwargs = {"dirs_exist_ok": True} if sys.version_info >= (3, 8) else {}
        shutil.copytree(bundled_presets, presets_dir, **kwargs)

        logger.info(f"Copy addon presets to: {presets_dir}")
