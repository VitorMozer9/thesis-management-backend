from rest_framework import serializers


class LoginSerializer(serializers.Serializer):

    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(max_length=4096, trim_whitespace=False)

    def validate(self, attrs):
        unexpected = set(self.initial_data) - set(self.fields)

        if unexpected:
            raise serializers.ValidationError({"detail": "Unexpected fields: " + ", ".join(sorted(unexpected))})

        return attrs


class ProfileSerializer(serializers.Serializer):

    id = serializers.UUIDField()
    name = serializers.CharField()
    email = serializers.EmailField()
    role = serializers.CharField()
    academic_id = serializers.UUIDField()
    course_id = serializers.UUIDField(allow_null=True)
    is_active = serializers.BooleanField()
