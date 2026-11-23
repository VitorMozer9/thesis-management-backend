from django.conf import settings

from defense.application import DefenseService
from defense.adapters.outbound.repository import Repository
from defense.adapters.outbound.theses import ThesisClient


def build_service():
    return DefenseService(Repository(), ThesisClient(settings.THESIS_API_URL))
