from uuid import UUID

from django.db.models import BooleanField, Q
from django.db.models.expressions import RawSQL
from django.utils import timezone

from thesis.adapters.outbound.persistence.mappers import ThesisMapper
from thesis.adapters.outbound.persistence.models import ThesisModel
from thesis.application.identity import AcademicIdentity
from thesis.application.exceptions import ThesisNotFoundError
from thesis.application.ports.thesis_repository import ThesisRepository
from thesis.domain.entities.thesis import Thesis
from thesis.domain.enums.thesis_status import ThesisStatus
from thesis.domain.exceptions import ThesisNotEditableError


class DjangoThesisRepository(ThesisRepository):

    def __init__(self, actor: AcademicIdentity | None = None):
        self.records = ThesisModel.objects.all()
        if actor is not None:
            self.records = self.records.filter(**actor.scope())

    def save(self, thesis: Thesis) -> Thesis:

        model_data = ThesisMapper.to_model_data(thesis)

        model, _ = ThesisModel.objects.update_or_create(
            id=thesis.id,
            defaults=model_data,
        )

        return ThesisMapper.to_domain(model)

    def find_by_id(self, thesis_id: UUID) -> Thesis | None:

        model = self.records.filter(
            id=thesis_id
        ).first()

        if model is None:
            return None

        return ThesisMapper.to_domain(model)

    def find_by_id_for_update(self, thesis_id: UUID) -> Thesis | None:
        model = self.records.select_for_update().filter(id=thesis_id).first()
        return ThesisMapper.to_domain(model) if model is not None else None

    def list(
        self,
        *,
        student_id: UUID | None,
        advisor_id: UUID | None,
        course_id: UUID | None,
        status: ThesisStatus | None,
        search: str | None,
        offset: int,
        limit: int,
    ) -> list[Thesis]:
        filters = {
            "student_id": student_id,
            "advisor_id": advisor_id,
            "course_id": course_id,
            "status": status,
        }
        queryset = self.records.filter(
            **{field: value for field, value in filters.items() if value is not None}
        )

        if search is not None:
            keyword_match = RawSQL(
                """
                EXISTS (
                    SELECT 1 FROM jsonb_array_elements_text(keywords) AS keyword(value)
                    WHERE strpos(lower(keyword.value), lower(%s)) > 0
                )
                """,
                (search,),
                output_field=BooleanField(),
            )
            queryset = queryset.filter(Q(title__icontains=search) | Q(keyword_match))

        ordered = queryset.order_by("-created_at", "-id")
        page = ordered[offset:offset + limit]

        return [ThesisMapper.to_domain(model) for model in page]

    def update_draft(self, thesis: Thesis, *, previous: Thesis | None = None) -> Thesis:
        model_data = ThesisMapper.to_model_data(thesis)

        candidates = self.records.filter(
            id=thesis.id,
            status=ThesisStatus.DRAFT,
        )
        if previous is not None:
            candidates = candidates.filter(**ThesisMapper.to_model_data(previous))

        updated = candidates.update(**model_data, updated_at=timezone.now())

        if updated:
            return thesis

        if not self.records.filter(id=thesis.id).exists():
            raise ThesisNotFoundError(f"Thesis {thesis.id} not found.")

        raise ThesisNotEditableError("The thesis changed or is no longer a draft.")

    def delete(self, thesis_id: UUID) -> None:
        self.records.filter(id=thesis_id).delete()
