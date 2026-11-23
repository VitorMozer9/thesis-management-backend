from django.shortcuts import get_object_or_404
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from config.dependencies import build_service
from defense.domain import DefenseError
from . import serializers as schema


def validated(serializer, data):
    instance = serializer(data=data)
    instance.is_valid(raise_exception=True)
    return instance.validated_data


class Base(APIView):
    def handle_exception(self, exc):
        if isinstance(exc, DefenseError):
            return Response({"detail": str(exc)}, status=exc.status)
        return super().handle_exception(exc)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response

    def visible(self, service, request, defense_id):
        return get_object_or_404(service.repo.visible(request.user), pk=defense_id)


class Collection(Base):
    def get(self, request):
        filters = validated(schema.Filters, request.query_params)
        size = filters.pop("page_size")
        offset = (filters.pop("page") - 1) * size
        records = list(build_service().repo.visible(request.user).filter(**filters)
                       .order_by("-created_at", "id")[offset:offset + size + 1])
        return Response({"results": schema.DefenseOutput(records[:size], many=True).data, "has_next": len(records) > size})

    def post(self, request):
        fields = validated(schema.Proposal, request.data)
        defense = build_service().create(fields["thesis_id"], request.user, request.auth)
        return Response(schema.DefenseOutput(defense).data, status=201)


class Detail(Base):
    def get(self, request, defense_id):
        defense = self.visible(build_service(), request, defense_id)
        return Response(schema.DefenseOutput(defense).data)


class Members(Base):
    def get(self, request, defense_id):
        service = build_service()
        defense = self.visible(service, request, defense_id)
        members = service.repo.members(defense)
        if request.user.role == "student":
            members = []
        return Response(schema.MemberOutput(members, many=True).data)

    def post(self, request, defense_id):
        fields = validated(schema.Invite, request.data)
        member, token = build_service().invite(defense_id, request.user, fields)
        body = dict(schema.MemberOutput(member).data)
        if token:
            body.update(token=token, expires_at=member.expires_at.isoformat())
        return Response(body, status=201)


class MemberDetail(Base):
    def delete(self, request, defense_id, member_id):
        build_service().remove(defense_id, member_id, request.user)
        return Response(status=204)


class InternalResponse(Base):
    def post(self, request, defense_id, member_id):
        fields = validated(schema.Reply, request.data)
        member = build_service().respond(defense_id, member_id, actor=request.user, **fields)
        return Response({"invite_status": member.invite_status})


class ExternalResponse(Base):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, defense_id, member_id):
        fields = validated(schema.ExternalReply, request.data)
        member = build_service().respond(defense_id, member_id, **fields)
        return Response({"invite_status": member.invite_status})


class Schedule(Base):
    def post(self, request, defense_id):
        fields = validated(schema.Schedule, request.data)
        defense = build_service().schedule(defense_id, request.user, request.auth, fields)
        return Response(schema.DefenseOutput(defense).data)


class Transition(Base):
    action = None

    def post(self, request, defense_id):
        validated(schema.Strict, request.data)
        defense = build_service().transition(defense_id, request.user, self.action)
        return Response(schema.DefenseOutput(defense).data)


class Evaluations(Base):
    def get(self, request, defense_id):
        service = build_service()
        defense = self.visible(service, request, defense_id)
        try:
            service.manage(defense, request.user)
        except DefenseError:
            member = service.repo.evaluator(defense, request.user)
            evaluations = [item for item in service.repo.evaluations(defense) if item.member_id == member.id]
        else:
            evaluations = service.repo.evaluations(defense)
        return Response(schema.ScoreOutput(evaluations, many=True).data)

    def post(self, request, defense_id):
        fields = validated(schema.Score, request.data)
        evaluation = build_service().evaluate(defense_id, request.user, fields)
        return Response(schema.ScoreOutput(evaluation).data, status=201)


class Result(Base):
    def get(self, request, defense_id):
        defense = self.visible(build_service(), request, defense_id)
        if not defense.result:
            return Response({"detail": "Resultado ainda não fechado."}, status=409)
        return Response({"result": defense.result, "average": str(defense.average)})
