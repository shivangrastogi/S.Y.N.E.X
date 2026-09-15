"""Process-wide dxcam (Desktop Duplication) singleton.

dxcam misbehaves when create()/release() are cycled — its internal registry
can hand back a dead camera. So the whole process shares ONE instance:

  * JPEG path (relay screen share) calls ``get().grab()`` — change-driven.
  * H.264 path (LAN video stream) calls ``get().start(target_fps=…,
    video_mode=True)`` / ``get_latest_frame()`` / ``stop()``.

The two paths never run concurrently (cloud_bridge's stream loop picks one),
so simple sharing is safe. The camera is only released at process exit.
"""
from __future__ import annotations

import logging
import threading
from typing import Optional

log = logging.getLogger(__name__)

_cam = None
_LOCK = threading.Lock()


def get():
    """The shared dxcam camera, or None when dxcam is unavailable."""
    global _cam
    with _LOCK:
        if _cam is None:
            try:
                import dxcam
                _cam = dxcam.create(output_color="BGR")
                log.info("[dxcap] dxcam camera created")
            except Exception as e:
                log.info("[dxcap] dxcam unavailable: %s", e)
                _cam = None
        return _cam


def available() -> bool:
    return get() is not None
