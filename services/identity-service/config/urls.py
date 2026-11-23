from django.urls import include, path


urlpatterns = [
    path("api/auth/", include("identity.adapters.inbound.rest.urls")),
]
