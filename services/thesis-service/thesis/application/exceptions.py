class ThesisNotFoundError(Exception):
    """Raised when a thesis cannot be found."""
    pass

class EventPublicationError(Exception):
    """Raised when a domain event cannot be published."""
    pass