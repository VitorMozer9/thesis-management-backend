from django.urls import path

from defense.adapters.inbound import views
from defense.adapters.inbound.verification import CompletedDefense


from defense.adapters.notification_lookup import notification_lookup


urlpatterns = [
    path("internal/notification-events/<uuid:event_id>/", notification_lookup),
    path("internal/completed-defenses/<uuid:defense_id>/", CompletedDefense.as_view()),
    path("api/defenses/", views.Collection.as_view()),
    path("api/defenses/<uuid:defense_id>/", views.Detail.as_view()),
    path("api/defenses/<uuid:defense_id>/members/", views.Members.as_view()),
    path("api/defenses/<uuid:defense_id>/members/<uuid:member_id>/", views.MemberDetail.as_view()),
    path("api/defenses/<uuid:defense_id>/members/<uuid:member_id>/response/", views.InternalResponse.as_view()),
    path("api/defenses/<uuid:defense_id>/members/<uuid:member_id>/external-response/", views.ExternalResponse.as_view()),
    path("api/defenses/<uuid:defense_id>/schedule/", views.Schedule.as_view()),
    path("api/defenses/<uuid:defense_id>/cancel/", views.Transition.as_view(action="cancel")),
    path("api/defenses/<uuid:defense_id>/hold/", views.Transition.as_view(action="hold")),
    path("api/defenses/<uuid:defense_id>/evaluations/", views.Evaluations.as_view()),
    path("api/defenses/<uuid:defense_id>/result/", views.Result.as_view()),
]
