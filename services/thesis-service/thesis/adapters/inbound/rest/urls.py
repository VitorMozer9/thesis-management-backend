from django.urls import path

from thesis.adapters.inbound.rest.views import (
    ThesisDetailView,
    ThesisPdfUploadView,
    ThesisReviewView,
    ThesisSubmitView,
    ThesisUploadStatusView,
    ThesisView,
)
from thesis.domain.enums.thesis_status import ThesisStatus

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

    path(
        "theses/<uuid:thesis_id>/submit/",
        ThesisSubmitView.as_view(),
        name="thesis-submit",
    ),
    path(
        "theses/<uuid:thesis_id>/approve/",
        ThesisReviewView.as_view(decision=ThesisStatus.ADVISOR_APPROVED),
        name="thesis-approve",
    ),
    path(
        "theses/<uuid:thesis_id>/reject/",
        ThesisReviewView.as_view(decision=ThesisStatus.ADVISOR_REJECTED),
        name="thesis-reject",
    ),
]
