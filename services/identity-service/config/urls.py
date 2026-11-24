from django.urls import include, path


from identity.adapters.notification_lookup import notification_lookup


urlpatterns = [
    path("internal/notification-contacts/<uuid:academic_id>/", notification_lookup),
    path("api/auth/", include("identity.adapters.inbound.rest.urls")),
    path("api/users/", include("identity.adapters.inbound.rest.user_urls")),
]
