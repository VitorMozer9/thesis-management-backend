from django.urls import path

from notifications.adapters.views import Detail, Notifications


urlpatterns = [
    path("api/notifications/", Notifications.as_view()),
    path("api/notifications/<uuid:notification_id>/", Detail.as_view()),
]
