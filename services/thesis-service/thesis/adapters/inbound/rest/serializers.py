from rest_framework import serializers

from thesis.application.use_case.list_theses import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE,
    MAX_PAGE_SIZE,
    MAX_SEARCH_LENGTH,
)
from thesis.domain.enums.thesis_status import ThesisStatus


class CreateThesisSerializer(serializers.Serializer):

    title = serializers.CharField(
        max_length=255,
        allow_blank=False,
    )

    abstract = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
    )

    student_id = serializers.UUIDField()

    course_id = serializers.UUIDField()


class ThesisResponseSerializer(serializers.Serializer):

    id = serializers.UUIDField()

    title = serializers.CharField()

    abstract = serializers.CharField()

    student_id = serializers.UUIDField()

    course_id = serializers.UUIDField()

    status = serializers.CharField()

    file_key = serializers.CharField(allow_null=True)

    file_sha256 = serializers.CharField(allow_null=True)

    advisor_id = serializers.UUIDField(required=False)


class ListThesesQuerySerializer(serializers.Serializer):

    student_id = serializers.UUIDField(required=False)
    advisor_id = serializers.UUIDField(required=False)
    course_id = serializers.UUIDField(required=False)
    status = serializers.ChoiceField(choices=ThesisStatus, required=False)
    search = serializers.CharField(required=False, max_length=MAX_SEARCH_LENGTH)
    page = serializers.IntegerField(min_value=1, max_value=MAX_PAGE, default=1)
    page_size = serializers.IntegerField(
        min_value=1,
        max_value=MAX_PAGE_SIZE,
        default=DEFAULT_PAGE_SIZE,
    )


class UpdateThesisSerializer(serializers.Serializer):

    title = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=False,
    )

    abstract = serializers.CharField(
        required=False,
        allow_blank=True,
    )

    keywords = serializers.ListField(
        child=serializers.CharField(
            allow_blank=False
        ),
        required=False,
        allow_empty=True,
    )

    advisor_id = serializers.UUIDField(required=False)

    def validate_keywords(self, value):
        return tuple(value)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError(
                "At least one field must be provided."
            )

        return attrs


class UploadThesisPdfSerializer(serializers.Serializer):

    file = serializers.FileField(
        allow_empty_file=False,
    )