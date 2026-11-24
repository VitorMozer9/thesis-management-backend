from django.conf import settings
from django.utils.timezone import now

from notifications.adapters.contacts import Contacts
from notifications.adapters.mail import SMTP
from notifications.adapters.records import Records
from notifications.application import ProcessNotifications


def processor():
    return ProcessNotifications(Records(), Contacts(settings.LOOKUP_ENDPOINTS), SMTP(), now, settings.MAX_ATTEMPTS)
