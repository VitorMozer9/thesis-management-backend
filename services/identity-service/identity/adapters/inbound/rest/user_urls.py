from django.urls import path

from identity.adapters.inbound.rest.views import UserActivationView, UserCollectionView, UserDetailView


urlpatterns = [
    path("", UserCollectionView.as_view(), name="identity-users"),
    path("<uuid:account_id>/", UserDetailView.as_view(), name="identity-user"),
    path(
        "<uuid:account_id>/deactivate/",
        UserActivationView.as_view(active=False),
        name="identity-user-deactivate",
    ),
    path(
        "<uuid:account_id>/activate/",
        UserActivationView.as_view(active=True),
        name="identity-user-activate",
    ),
]
