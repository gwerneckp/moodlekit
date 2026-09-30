"""Use Moodle programmatically with your existing browser login (works with SSO)."""

from .client import Activity, Course, Event, File, Moodle, MoodleError, NotLoggedIn, Page
from .sync import Change, Sync, SyncReport
from .utils import Utils

__all__ = ["Activity", "Change", "Course", "Event", "File", "Moodle", "MoodleError",
           "NotLoggedIn", "Page", "Sync", "SyncReport", "Utils"]
__version__ = "0.1.0"
