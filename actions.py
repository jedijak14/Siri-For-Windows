"""Explicitly confirmed, allowlisted Windows actions."""

import os
import sys
from pathlib import Path


class ActionError(RuntimeError):
    """Raised when a requested local action cannot be completed."""


def _open_location(target):
    if sys.platform != "win32":
        raise ActionError("Opening Windows locations is available only on Windows.")
    try:
        os.startfile(str(target))
    except OSError as exc:
        raise ActionError(f"Could not open {target}: {exc}") from exc


def open_photos():
    """Launch the installed Windows Photos app via its registered URI."""
    _open_location("ms-photos:")


def open_onedrive():
    """Open the current user's conventional OneDrive folder, if present."""
    candidate = Path.home() / "OneDrive"
    if not candidate.is_dir():
        raise ActionError(f"OneDrive folder was not found at {candidate}.")
    _open_location(candidate)
