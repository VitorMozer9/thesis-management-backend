from rest_framework import serializers

from identity.domain.account import MAX_NAME_LENGTH, Role


ROLE_CHOICES = [role.value for role in Role]


class StrictSerializer(serializers.Serializer):

    def validate(self, attrs):
        unexpected = set(self.initial_data) - set(self.fields)

        if unexpected:
            raise serializers.ValidationError({"detail": "Unexpected fields: " + ", ".join(sorted(unexpected))})

        return attrs


class LoginSerializer(StrictSerializer):

    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(max_length=4096, trim_whitespace=False)


class ProfileSerializer(serializers.Serializer):

    id = serializers.UUIDField()
    name = serializers.CharField()
    email = serializers.EmailField()
    role = serializers.CharField()
    academic_id = serializers.UUIDField()
    course_id = serializers.UUIDField(allow_null=True)
    is_active = serializers.BooleanField()


class AccountCreateSerializer(StrictSerializer):

    name = serializers.CharField(max_length=MAX_NAME_LENGTH)
    email = serializers.EmailField(max_length=254)
    role = serializers.ChoiceField(choices=ROLE_CHOICES)
    course_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    academic_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    password = serializers.CharField(write_only=True, max_length=4096, trim_whitespace=False)


class AccountUpdateSerializer(StrictSerializer):

    name = serializers.CharField(required=False, max_length=MAX_NAME_LENGTH)
    email = serializers.EmailField(required=False, max_length=254)
    role = serializers.ChoiceField(required=False, choices=ROLE_CHOICES)
    course_id = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, attrs):
        attrs = super().validate(attrs)

        if not attrs:
            raise serializers.ValidationError({"detail": "At least one field must be provided."})

        return attrs


class AccountQuerySerializer(StrictSerializer):

    role = serializers.ChoiceField(required=False, choices=ROLE_CHOICES)
    course_id = serializers.UUIDField(required=False)
    is_active = serializers.BooleanField(required=False, allow_null=True, default=None)
    search = serializers.CharField(required=False, max_length=100)
    page = serializers.IntegerField(required=False, min_value=1, default=1)
    page_size = serializers.IntegerField(required=False, min_value=1, max_value=100, default=20)
