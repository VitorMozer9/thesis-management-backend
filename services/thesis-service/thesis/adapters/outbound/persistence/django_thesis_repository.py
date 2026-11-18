from uuid import UUID

from thesis.domain.entities.thesis import Thesis

from thesis.application.ports.thesis_repository import ThesisRepository

from thesis.adapters.outbound.persistence.models import ThesisModel

from thesis.adapters.outbound.persistence.mappers import ThesisMapper


class DjangoThesisRepository(ThesisRepository):

    def save(self, thesis: Thesis) -> Thesis:

        model_data = ThesisMapper.to_model_data(thesis)

        model, _ = ThesisModel.objects.update_or_create(
            id=thesis.id,
            defaults=model_data,
        )

        return ThesisMapper.to_domain(model)

    def find_by_id(self, thesis_id: UUID) -> Thesis | None:

        model = ThesisModel.objects.filter(
            id=thesis_id
        ).first()

        if model is None:
            return None

        return ThesisMapper.to_domain(model)