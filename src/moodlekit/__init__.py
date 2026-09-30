"""Use Moodle programmatically with your existing browser login (works with SSO)."""

from .browser import Browser
from .client import Activity, Course, Event, File, Moodle, MoodleError, NotLoggedIn, Page
from .utils import Utils

__all__ = ["Activity", "Browser", "Course", "Event", "File", "Moodle", "MoodleError",
           "NotLoggedIn", "Page", "Utils"]
__version__ = "0.1.0"
