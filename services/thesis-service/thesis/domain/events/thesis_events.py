from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import ClassVar
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class ThesisCreatedEvent:

    thesis_id: UUID

    event_id: UUID = field(default_factory=uuid4)

    occurred_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    event_type: ClassVar[str] = "thesis.created"

    version: ClassVar[int] = 1


@dataclass(frozen=True, slots=True)
class ThesisSubmittedEvent:

    thesis_id: UUID

    event_id: UUID = field(default_factory=uuid4)

    occurred_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    event_type: ClassVar[str] = "thesis.submitted"

    version: ClassVar[int] = 1

ThesisEvent = ThesisCreatedEvent | ThesisSubmittedEvent