from dataclasses import fields

from django.db import IntegrityError, connection, transaction
from django.db.models import Q

from defense import domain
from defense.domain import DefenseError, Forbidden, Missing, Status
from django.utils import timezone

from .models import Audit, Defense, Evaluation, Member, Outbox


def entity(entity_class, record):
    return entity_class(**{field.name: getattr(record, field.name) for field in fields(entity_class)})


class Repository:
    transaction = staticmethod(transaction.atomic)

    def lock_schedule(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [870431002])

    def get(self, defense_id, lock=False):
        query = Defense.objects.select_for_update() if lock else Defense.objects.all()
        defense = query.filter(pk=defense_id).first()
        if defense is None:
            raise Missing("Banca inexistente.")
        return entity(domain.Defense, defense)

    def visible(self, actor):
        query = Defense.objects.filter(course_id=actor.course_id)
        if actor.role == "student":
            return query.filter(student_id=actor.academic_id)
        if actor.role == "advisor":
            return query.filter(Q(advisor_id=actor.academic_id) | Q(members__academic_id=actor.academic_id)).distinct()
        if actor.role == "coordinator":
            return query
        return query.none()

    def create(self, thesis):
        try:
            record = Defense.objects.create(
                thesis_id=thesis.id, course_id=thesis.course_id,
                student_id=thesis.student_id, advisor_id=thesis.advisor_id,
            )
            return entity(domain.Defense, record)
        except IntegrityError as exc:
            raise DefenseError("Já existe uma banca ativa para esta monografia.") from exc

    def invite(self, defense, fields):
        try:
            return entity(domain.DefenseMember, Member.objects.create(defense_id=defense.id, **fields))
        except IntegrityError as exc:
            raise DefenseError("O membro já pertence à banca.") from exc

    def member(self, defense, member_id):
        member = Member.objects.filter(defense_id=defense.id).filter(pk=member_id).first()
        if member is None:
            raise Missing("Convite inexistente.")
        return entity(domain.DefenseMember, member)

    def remove(self, member):
        Member.objects.filter(pk=member.id).delete()

    def members(self, defense):
        return [entity(domain.DefenseMember, row) for row in Member.objects.filter(defense_id=defense.id)]

    def conflicts(self, defense, members, fields):
        other = Defense.objects.filter(
            status=Status.SCHEDULED, starts_at__lt=fields["ends_at"], ends_at__gt=fields["starts_at"],
        ).exclude(pk=defense.id)
        academic_ids = [member.academic_id for member in members if member.academic_id]
        emails = [member.email for member in members if member.kind == "external"]
        people = set(academic_ids) | {defense.student_id, defense.advisor_id}
        conditions = Q(
            student_id__in=people,
        ) | Q(advisor_id__in=people) | Q(members__academic_id__in=people) | Q(members__email__in=emails)
        if fields.get("venue"):
            conditions |= Q(venue__iexact=fields["venue"])
        if fields.get("meeting_url"):
            conditions |= Q(meeting_url=fields["meeting_url"])
        return other.filter(conditions).exists()

    def evaluator(self, defense, actor):
        if actor.course_id == defense.course_id and actor.role in ("advisor", "coordinator"):
            member = Member.objects.filter(defense_id=defense.id).filter(
                kind="internal", academic_id=actor.academic_id, invite_status="confirmed",
            ).first()
            if member is not None:
                return entity(domain.DefenseMember, member)
        raise Forbidden("A avaliação é exclusiva do avaliador interno confirmado.")

    def evaluate(self, member, fields):
        try:
            return entity(domain.DefenseEvaluation, Evaluation.objects.create(member_id=member.id, **fields))
        except IntegrityError as exc:
            raise DefenseError("O membro já registrou uma avaliação.") from exc

    def evaluations(self, defense):
        rows = Evaluation.objects.filter(member__defense_id=defense.id).order_by("created_at")
        return [entity(domain.DefenseEvaluation, row) for row in rows]

    def evaluator_count(self, defense):
        return Member.objects.filter(defense_id=defense.id).filter(kind="internal", invite_status="confirmed").count()

    def update(self, model, **fields):
        if isinstance(model, domain.Defense):
            records = Defense.objects
            fields["updated_at"] = timezone.now()
        else:
            records = Member.objects

        records.filter(pk=model.id).update(**fields)
        for key, value in fields.items():
            setattr(model, key, value)

    def audit(self, defense, actor_id, action):
        Audit.objects.create(defense_id=defense.id, actor_id=actor_id, action=action)

    def event(self, defense, event_type, data):
        Outbox.objects.create(
            defense_id=defense.id, event_type=event_type,
            data={"defense_id": str(defense.id), "thesis_id": str(defense.thesis_id),
                  "course_id": str(defense.course_id), **data},
        )
