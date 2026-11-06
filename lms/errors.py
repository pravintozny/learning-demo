"""Domain exceptions for the LMS."""


class LMSError(Exception):
    """Base class for all LMS errors."""


class NotFoundError(LMSError):
    pass


class ValidationError(LMSError):
    pass


class EnrollmentError(LMSError):
    """Enrollment constraint violated (duplicate, capacity, closed course)."""


class PrerequisiteError(EnrollmentError):
    """Student has not completed required prerequisite courses."""


class AttemptLimitError(LMSError):
    pass
