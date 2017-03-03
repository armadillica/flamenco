"""Flamenco-specific exceptions."""


class FlamencoException(Exception):
    """Base exception for all Flamenco-specific exceptions."""


class JobSettingError(FlamencoException):
    """Raised when a job's settings contains errors."""
