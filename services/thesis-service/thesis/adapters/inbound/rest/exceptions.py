from rest_framework import status
from rest_framework.exceptions import APIException


class ConflictError(APIException):

    status_code = status.HTTP_409_CONFLICT

    default_detail = "Resource state conflict."

    default_code = "conflict"