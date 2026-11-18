from thesis.domain.entities.thesis import Thesis
from thesis.domain.enums.thesis_status import ThesisStatus

from thesis.adapters.outbound.persistence.models import ThesisModel


class ThesisMapper:

    @staticmethod
    def to_domain(model: ThesisModel) -> Thesis:
        return Thesis(
            id=model.id,
            title=model.title,
            abstract=model.abstract,
            student_id=model.student_id,
            course_id=model.course_id,
            advisor_id=model.advisor_id,
            keywords=tuple(model.keywords),
            file_key=model.file_key,
            file_sha256=model.file_sha256,
            status=ThesisStatus(model.status),
        )

    @staticmethod
    def to_model_data(thesis: Thesis) -> dict:
        return {
            "title": thesis.title,
            "abstract": thesis.abstract,
            "student_id": thesis.student_id,
            "course_id": thesis.course_id,
            "advisor_id": thesis.advisor_id,
            "keywords": list(thesis.keywords),
            "file_key": thesis.file_key,
            "file_sha256": thesis.file_sha256,
            "status": thesis.status.value,
        }