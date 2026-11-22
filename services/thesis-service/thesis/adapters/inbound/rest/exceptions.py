from rest_framework import status
from rest_framework.exceptions import APIException

class ConflictError(APIException):

    status_code = status.HTTP_409_CONFLICT

    default_detail = "Resource state conflict."

    default_code = "conflict"


class ServiceUnavailableError(APIException):

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    default_detail = "Service temporarily unavailable."

    default_code = "service_unavailable"