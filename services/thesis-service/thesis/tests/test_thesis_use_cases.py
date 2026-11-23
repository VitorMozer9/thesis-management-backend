import unittest

from uuid import uuid4

from thesis.domain.entities.thesis import Thesis
from thesis.domain.exceptions import ThesisNotEditableError

from thesis.application.exceptions import ThesisNotFoundError
from thesis.application.use_case.get_thesis import GetThesisUseCase
from thesis.application.use_case.update_thesis import UpdateThesisUseCase

from contextlib import AbstractContextManager, nullcontext
from uuid import UUID

from thesis.application.ports.thesis_lock import ThesisLockPort

from thesis.application.ports.outbox_repository import (
    OutboxRepositoryPort,
)

from thesis.domain.events.thesis_events import (
    ThesisCreatedEvent,
)

from contextlib import AbstractContextManager, nullcontext

from thesis.application.ports.unit_of_work import (
    UnitOfWorkPort,
)

from thesis.application.use_case.create_thesis import (
    CreateThesisUseCase,
)

from thesis.domain.enums.thesis_status import ThesisStatus

class InMemoryThesisRepository:

    def __init__(self):
        self.theses = {}

    def save(self, thesis):
        self.theses[thesis.id] = thesis
        return thesis

    def find_by_id(self, thesis_id):
        return self.theses.get(thesis_id)


class ThesisUseCaseTests(unittest.TestCase):

    def setUp(self):
        self.repository = InMemoryThesisRepository()

        self.thesis = Thesis.create_draft(
            title="Distributed Systems",
            abstract="A study about distributed systems.",
            student_id=uuid4(),
            course_id=uuid4(),
        )

        self.repository.save(self.thesis)

    def test_get_existing_thesis(self):
        use_case = GetThesisUseCase(
            repository=self.repository
        )

        result = use_case.execute(self.thesis.id)

        self.assertEqual(result.id, self.thesis.id)
        self.assertEqual(result.title, self.thesis.title)

    def test_get_nonexistent_thesis(self):
        use_case = GetThesisUseCase(
            repository=self.repository
        )

        with self.assertRaises(ThesisNotFoundError):
            use_case.execute(uuid4())

    def test_update_draft_title(self):
        use_case = UpdateThesisUseCase(
            repository=self.repository,
            thesis_lock=FakeThesisLock(),
        )

        updated = use_case.execute(
            thesis_id=self.thesis.id,
            title="Hexagonal Architecture",
        )

        self.assertEqual(
            updated.title,
            "Hexagonal Architecture",
        )

        stored = self.repository.find_by_id(self.thesis.id)

        self.assertEqual(stored.title, updated.title)

    def test_update_only_selected_field(self):
        use_case = UpdateThesisUseCase(
            repository=self.repository,
            thesis_lock=FakeThesisLock(),
        )

        updated = use_case.execute(
            thesis_id=self.thesis.id,
            abstract="Updated abstract.",
        )

        self.assertEqual(
            updated.title,
            "Distributed Systems",
        )

        self.assertEqual(
            updated.abstract,
            "Updated abstract.",
        )

    def test_cannot_update_submitted_thesis(self):
        submitted = (
            self.thesis
            .change_keywords(("distributed systems",))
            .assign_advisor(uuid4())
            .attach_file("theses/document.pdf", "a" * 64)
            .submit()
        )

        self.repository.save(submitted)

        use_case = UpdateThesisUseCase(
            repository=self.repository,
            thesis_lock=FakeThesisLock(),
        )

        with self.assertRaises(ThesisNotEditableError):
            use_case.execute(
                thesis_id=submitted.id,
                title="Forbidden change",
            )

def test_create_thesis_with_outbox_event(self):

    outbox_repository = FakeOutboxRepository()

    use_case = CreateThesisUseCase(
        repository=self.repository,
        outbox_repository=outbox_repository,
        unit_of_work=FakeUnitOfWork(),
    )

    student_id = uuid4()
    course_id = uuid4()

    thesis = use_case.execute(
        title="Hexagonal Architecture",
        abstract="A study about software architecture.",
        student_id=student_id,
        course_id=course_id,
    )

    saved_thesis = self.repository.find_by_id(thesis.id)

    self.assertIsNotNone(saved_thesis)
    self.assertEqual(
        saved_thesis.title,
        "Hexagonal Architecture",
    )

    self.assertEqual(
        saved_thesis.status,
        ThesisStatus.DRAFT,
    )

    self.assertEqual(
        len(outbox_repository.events),
        1,
    )

    event = outbox_repository.events[0]

    self.assertEqual(
        event.thesis_id,
        thesis.id,
    )

    self.assertEqual(
        event.event_type,
        "thesis.created",
    )

class FakeThesisLock(ThesisLockPort):

    def lock(
        self,
        thesis_id: UUID
    ) -> AbstractContextManager[None]:

        return nullcontext()

class FakeOutboxRepository(OutboxRepositoryPort):

    def __init__(self):
        self.events = []

    def add(
        self,
        event: ThesisCreatedEvent,
    ) -> None:

        self.events.append(event)

class FakeUnitOfWork(UnitOfWorkPort):

    def transaction(
        self,
    ) -> AbstractContextManager[None]:

        return nullcontext()