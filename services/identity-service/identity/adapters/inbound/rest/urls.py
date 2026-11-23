from django.urls import path

from identity.adapters.inbound.rest.views import LoginView, ProfileView


urlpatterns = [
    path("login/", LoginView.as_view(), name="identity-login"),
    path("me/", ProfileView.as_view(), name="identity-profile"),
]
