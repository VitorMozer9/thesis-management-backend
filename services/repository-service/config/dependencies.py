from django.conf import settings

from repository.adapters.documents import Documents
from repository.adapters.defenses import DefenseClient
from repository.adapters.records import Records
from repository.adapters.theses import ThesisClient
from repository.application import PublicationService


def service():
    return PublicationService(Records(), Documents(settings.MEDIA_ROOT), ThesisClient(settings.THESIS_API_URL),
                              DefenseClient(settings.DEFENSE_API_URL, settings.VERIFICATION_KEY))
