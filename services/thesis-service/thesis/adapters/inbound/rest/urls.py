from django.urls import path

from thesis.adapters.inbound.rest.views import (ThesisView,ThesisDetailView,ThesisPdfUploadView, ThesisUploadStatusView)

urlpatterns = [
    path(
        "theses/",
        ThesisView.as_view(),
        name="thesis-create",
    ),

    path(
        "theses/<uuid:thesis_id>/",
        ThesisDetailView.as_view(),
        name="thesis-detail",
    ),

    path(
        "theses/<uuid:thesis_id>/pdf/",
        ThesisPdfUploadView.as_view(),
        name="thesis-pdf-upload",
    ),

    path(
        "theses/<uuid:thesis_id>/upload-status/",
        ThesisUploadStatusView.as_view(),
        name="thesis-upload-status",
    ),
]