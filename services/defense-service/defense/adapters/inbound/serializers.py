from datetime import timedelta

from rest_framework import serializers

from defense.domain import Status


class Strict(serializers.Serializer):
    def to_internal_value(self, data):
        if hasattr(data, "keys"):
            unexpected = set(data.keys()) - set(self.fields)
            if unexpected:
                raise serializers.ValidationError({key: "Campo desconhecido." for key in sorted(unexpected)})
            if hasattr(data, "getlist") and any(len(data.getlist(key)) > 1 for key in data):
                raise serializers.ValidationError("Campo repetido.")
        return super().to_internal_value(data)


class Proposal(Strict):
    thesis_id = serializers.UUIDField()


class Filters(Strict):
    thesis_id = serializers.UUIDField(required=False)
    status = serializers.ChoiceField(choices=list(Status), required=False)
    page = serializers.IntegerField(min_value=1, max_value=10000, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, default=20)


class Invite(Strict):
    kind = serializers.ChoiceField(choices=["internal", "external"])
    academic_id = serializers.UUIDField(required=False)
    name = serializers.CharField(max_length=200, required=False)
    email = serializers.EmailField(max_length=254, required=False)

    def validate(self, attrs):
        expected = {"kind", "academic_id"} if attrs["kind"] == "internal" else {"kind", "email", "name"}
        if set(attrs) != expected:
            raise serializers.ValidationError("Dados incompatíveis com o tipo de membro.")
        if "email" in attrs:
            attrs["email"] = attrs["email"].lower()
        return attrs


class Reply(Strict):
    accept = serializers.BooleanField()


class ExternalReply(Reply):
    token = serializers.RegexField(r"\A[A-Za-z0-9_-]{43}\Z", write_only=True, trim_whitespace=False)


class Schedule(Strict):
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    venue = serializers.CharField(max_length=255, required=False, default="")
    meeting_url = serializers.URLField(max_length=500, required=False, default="")

    def validate(self, attrs):
        if not timedelta(minutes=15) <= attrs["ends_at"] - attrs["starts_at"] <= timedelta(hours=8):
            raise serializers.ValidationError("Duração permitida de 15 minutos a 8 horas.")
        if bool(attrs["venue"]) == bool(attrs["meeting_url"]):
            raise serializers.ValidationError("Informe somente o local ou o link da reunião.")
        if attrs["meeting_url"] and not attrs["meeting_url"].startswith("https://"):
            raise serializers.ValidationError("O link deve utilizar HTTPS.")
        return attrs


class Score(Strict):
    grade = serializers.DecimalField(max_digits=4, decimal_places=2, min_value=0, max_value=10)
    opinion = serializers.CharField(max_length=5000)
    recommendation = serializers.ChoiceField(choices=["approved", "conditional", "rejected"])


class DefenseOutput(serializers.Serializer):
    id = serializers.UUIDField()
    thesis_id = serializers.UUIDField()
    course_id = serializers.UUIDField()
    status = serializers.CharField()
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    venue = serializers.CharField()
    meeting_url = serializers.CharField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class MemberOutput(serializers.Serializer):
    id = serializers.UUIDField()
    kind = serializers.CharField()
    academic_id = serializers.UUIDField()
    name = serializers.CharField()
    invite_status = serializers.CharField()


class ScoreOutput(serializers.Serializer):
    id = serializers.UUIDField()
    member_id = serializers.UUIDField()
    grade = serializers.DecimalField(max_digits=4, decimal_places=2)
    opinion = serializers.CharField()
    recommendation = serializers.CharField()
    created_at = serializers.DateTimeField()
