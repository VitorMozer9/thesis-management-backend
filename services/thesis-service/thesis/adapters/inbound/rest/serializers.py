from rest_framework import serializers


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