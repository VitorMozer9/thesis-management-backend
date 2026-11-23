from datetime import datetime, timedelta, timezone
from hashlib import sha256
from hmac import compare_digest
from secrets import token_urlsafe

from defense.domain import DefenseError, Forbidden, Missing, Status, calculate_result


class DefenseService:
    def __init__(self, repository, theses):
        self.repo = repository
        self.theses = theses

    def verify_thesis(self, thesis_id, actor, token):
        if actor.role not in ("coordinator", "advisor"):
            raise Forbidden("Operação reservada à coordenação e à orientação.")
        thesis = self.theses.get(thesis_id, token)
        if thesis.course_id != actor.course_id or (
            actor.role == "advisor" and thesis.advisor_id != actor.academic_id
        ):
            raise Missing("Monografia fora do escopo.")
        if thesis.status != "advisor_approved" or not thesis.advisor_id:
            raise DefenseError("A monografia precisa da aprovação do orientador.")
        return thesis

    def create(self, thesis_id, actor, token):
        thesis = self.verify_thesis(thesis_id, actor, token)
        with self.repo.transaction():
            defense = self.repo.create(thesis)
            self.repo.audit(defense, actor.account_id, "proposed")
            return defense

    def manage(self, defense, actor):
        if defense.course_id != actor.course_id or not (
            actor.role == "coordinator" or
            (actor.role == "advisor" and actor.academic_id == defense.advisor_id)
        ):
            raise Forbidden("Banca fora do escopo de gestão.")

    def invite(self, defense_id, actor, fields):
        with self.repo.transaction():
            defense = self.repo.get(defense_id, lock=True)
            self.manage(defense, actor)
            self.check_open(defense)

            token = None
            if fields["kind"] == "external":
                token = token_urlsafe(32)
                fields = {
                    **fields, "token_hash": self.digest(token),
                    "expires_at": datetime.now(timezone.utc) + timedelta(hours=48),
                }

            member = self.repo.invite(defense, fields)
            self.repo.update(defense, status=Status.WAITING)
            self.repo.audit(defense, actor.account_id, "member_invited")
            return member, token

    def remove(self, defense_id, member_id, actor):
        with self.repo.transaction():
            defense = self.repo.get(defense_id, lock=True)
            self.manage(defense, actor)
            self.check_open(defense)
            self.repo.remove(self.repo.member(defense, member_id))
            self.repo.audit(defense, actor.account_id, "member_removed")

    @staticmethod
    def check_open(defense):
        if defense.status not in (Status.PROPOSED, Status.WAITING):
            raise DefenseError("A composição da banca está fechada.")

    @staticmethod
    def digest(token):
        return sha256(token.encode()).hexdigest()

    def respond(self, defense_id, member_id, accept, *, actor=None, token=None):
        with self.repo.transaction():
            defense = self.repo.get(defense_id, lock=True)
            member = self.repo.member(defense, member_id)
            if actor is not None:
                authorized = (
                    member.kind == "internal" and actor.role in ("advisor", "coordinator")
                    and actor.course_id == defense.course_id and member.academic_id == actor.academic_id
                )
            else:
                authorized = (
                    member.kind == "external" and member.expires_at is not None
                    and member.expires_at > datetime.now(timezone.utc)
                    and compare_digest(member.token_hash, self.digest(token))
                )
            if not authorized:
                raise Forbidden("Convite inválido, expirado ou fora do escopo.")
            self.check_open(defense)
            if member.invite_status != "pending":
                raise DefenseError("O convite já foi respondido.")

            response = "confirmed" if accept else "declined"
            self.repo.update(member, invite_status=response, token_hash="", expires_at=None)
            self.repo.audit(defense, actor.account_id if actor else member.id, f"invite_{response}")
            return member

    def schedule(self, defense_id, actor, token, fields):
        prior = self.repo.get(defense_id)
        self.manage(prior, actor)
        thesis = self.verify_thesis(prior.thesis_id, actor, token)
        with self.repo.transaction():
            self.repo.lock_schedule()
            defense = self.repo.get(defense_id, lock=True)
            self.manage(defense, actor)
            self.check_open(defense)
            if (thesis.course_id, thesis.student_id, thesis.advisor_id) != (
                defense.course_id, defense.student_id, defense.advisor_id,
            ):
                raise DefenseError("Os vínculos acadêmicos da proposta mudaram.")

            members = self.repo.members(defense)
            if not any(m.kind == "internal" for m in members) or any(
                m.invite_status != "confirmed" for m in members
            ):
                raise DefenseError("Todos os convidados devem confirmar e é necessário um avaliador interno.")
            duration = fields["ends_at"] - fields["starts_at"]
            if not timedelta(minutes=15) <= duration <= timedelta(hours=8):
                raise DefenseError("Intervalo inválido.")
            if bool(fields.get("venue")) == bool(fields.get("meeting_url")):
                raise DefenseError("Informe apenas um local ou link.")
            if fields["starts_at"] <= datetime.now(timezone.utc):
                raise DefenseError("O agendamento precisa estar no futuro.")
            if self.repo.conflicts(defense, members, fields):
                raise DefenseError("Há conflito de horário com uma banca ativa.")

            self.repo.update(defense, **fields, status=Status.SCHEDULED)
            self.record(defense, actor, "scheduled", {
                "starts_at": defense.starts_at.isoformat(), "ends_at": defense.ends_at.isoformat(),
            })
            return defense

    def transition(self, defense_id, actor, action):
        with self.repo.transaction():
            defense = self.repo.get(defense_id, lock=True)
            self.manage(defense, actor)

            if action == "cancel":
                if defense.status in (Status.CANCELLED, Status.HELD):
                    raise DefenseError("A banca não pode ser cancelada neste estado.")
                self.repo.update(defense, status=Status.CANCELLED)
                self.record(defense, actor, "cancelled", {})
            else:
                if defense.status != Status.SCHEDULED or defense.ends_at > datetime.now(timezone.utc):
                    raise DefenseError("A defesa só pode ser registrada após o horário agendado.")
                self.repo.update(defense, status=Status.HELD)
                self.repo.audit(defense, actor.account_id, "held")
            return defense

    def evaluate(self, defense_id, actor, fields):
        with self.repo.transaction():
            defense = self.repo.get(defense_id, lock=True)
            member = self.repo.evaluator(defense, actor)
            if defense.status != Status.HELD or defense.result:
                raise DefenseError("A banca não está aberta para avaliações.")
            evaluation = self.repo.evaluate(member, fields)
            self.record(defense, actor, "evaluation_registered", {"evaluation_id": str(evaluation.id)})
            evaluations = self.repo.evaluations(defense)
            if len(evaluations) == self.repo.evaluator_count(defense):
                average, result = calculate_result(evaluations)
                self.repo.update(defense, average=average, result=result)
                self.record(defense, actor, "completed", {"average": str(average), "result": result})
            return evaluation

    def record(self, defense, actor, action, data):
        self.repo.audit(defense, actor.account_id, action)
        self.repo.event(defense, f"defense.{action}", data)
