from enum import StrEnum

class ThesisStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    ADVISOR_APPROVED = "advisor_approved"
    ADVISOR_REJECTED = "advisor_rejected"
    DEFENSE_APPROVED = "defense_approved"
    DEFENSE_REJECTED = "defense_rejected"
    PUBLISHED = "published"