from dataclasses import dataclass
from uuid import UUID


MESSAGES = {
    "thesis.submitted": ("Monografia submetida", "Uma monografia sob sua orientação foi submetida."),
    "defense.scheduled": ("Defesa agendada", "Uma banca da qual você participa foi agendada."),
    "defense.cancelled": ("Defesa cancelada", "Uma banca da qual você participa foi cancelada."),
    "repository.published": ("Monografia publicada", "Sua monografia está disponível no repositório público."),
}


@dataclass(frozen=True)
class Actor:
    account_id: UUID
    academic_id: UUID
    role: str
    course_id: UUID

    @property
    def is_authenticated(self):
        return True


class Failure(Exception):
    def __init__(self, code, *, permanent=False):
        self.code = code
        self.permanent = permanent
