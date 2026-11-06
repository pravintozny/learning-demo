"""A small in-memory Learning Management System."""
from .errors import (AttemptLimitError, EnrollmentError, LMSError, NotFoundError,
                     PrerequisiteError, ValidationError)
from .system import LMS

__all__ = ["LMS", "LMSError", "NotFoundError", "ValidationError", "EnrollmentError",
           "PrerequisiteError", "AttemptLimitError"]
