class ThesisDomainError(Exception):
    """Base exception for thesis domain errors."""
    pass


class InvalidThesisError(ThesisDomainError):
    """Raised when thesis data violates domain rules."""
    pass


class ThesisNotEditableError(ThesisDomainError):
    """Raised when editing a thesis is not allowed."""
    pass


class InvalidThesisStatusTransitionError(ThesisDomainError):
    """Raised when a status transition is not allowed."""
    pass


class ThesisSubmissionError(ThesisDomainError):
    """Raised when a thesis cannot be submitted."""
    pass