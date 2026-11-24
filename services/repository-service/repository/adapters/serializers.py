from collections.abc import Mapping

from rest_framework import serializers


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, Mapping) or set(data) - self.fields.keys():
            raise serializers.ValidationError({"detail": "Campos inválidos."})
        if hasattr(data, "getlist") and any(len(data.getlist(key)) != 1 for key in data):
            raise serializers.ValidationError({"detail": "Parâmetro repetido."})
        return super().to_internal_value(data)


class Metadata(StrictSerializer):
    title = serializers.CharField(max_length=255)
    author = serializers.CharField(max_length=200)
    advisor = serializers.CharField(max_length=200)
    keywords = serializers.ListField(child=serializers.CharField(max_length=100), min_length=1, max_length=30)
    reported_year = serializers.IntegerField(min_value=1900, max_value=9999, default=None)

    def validate_keywords(self, words):
        if any("\n" in word or "\r" in word for word in words):
            raise serializers.ValidationError("Palavra-chave inválida.")
        return "\n".join(words)


class Document(StrictSerializer):
    kind = serializers.ChoiceField(choices=["authorization", "final", "corrected"])
    file = serializers.FileField()
    sha256 = serializers.RegexField(r"\A[a-f0-9]{64}\Z")


class Search(StrictSerializer):
    title = serializers.CharField(max_length=255, required=False)
    author = serializers.CharField(max_length=200, required=False)
    advisor = serializers.CharField(max_length=200, required=False)
    keywords = serializers.CharField(max_length=200, required=False)
    course_id = serializers.UUIDField(required=False)
    year = serializers.IntegerField(min_value=1900, max_value=9999, required=False)
    page = serializers.IntegerField(min_value=1, max_value=10000, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, default=20)
