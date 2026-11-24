from django.urls import path

from repository.adapters.views import Catalog, Detail, Download, EditMetadata, RegisterDocument


from repository.adapters.notification_lookup import notification_lookup


urlpatterns = [
    path("internal/notification-events/<uuid:event_id>/", notification_lookup),
    path("api/repository/", Catalog.as_view()),
    path("api/repository/<uuid:thesis_id>/", Detail.as_view()),
    path("api/repository/<uuid:thesis_id>/pdf/", Download.as_view()),
    path("api/repository/admin/<uuid:thesis_id>/metadata/", EditMetadata.as_view()),
    path("api/repository/admin/<uuid:thesis_id>/documents/", RegisterDocument.as_view()),
]
