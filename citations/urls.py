from django.urls import include, path
from django.views.generic import RedirectView

from citations.views import (
    CitationAPIView,
    CitationsView,
    CitationView,
    ConfirmDeleteCitationView,
    EditCitationFormView,
    FundingStreamAPIView,
    FundingStreamsView,
    FundingStreamView,
    InstitutionAPIView,
    InstitutionsView,
    InstitutionView,
    NewCitationFormView,
    PartiesView,
    PartyAPIView,
    PartyView,
    ReviewerRequestView,
    SpecificCitationAPIView,
    SpecificPartyAPIView,
)

app_name = "citations"
urlpatterns = [
    path("", RedirectView.as_view(url="citations/")),
    path("parties/", PartiesView.as_view(), name="parties"),
    path("citations/", CitationsView.as_view(), name="citations"),
    path("institutions/", InstitutionsView.as_view(), name="institutions"),
    path("fundingstreams/", FundingStreamsView.as_view(), name="funders"),
    path("party/<str:pk>", PartyView.as_view(), name="party"),
    path("citation/<str:title>", CitationView.as_view(), name="citation"),
    path("citations/add", NewCitationFormView.as_view(), name="add_citation"),
    path(
        "citation/edit/<str:pk>",
        EditCitationFormView.as_view(),
        name="edit_citation",
    ),
    path(
        "citation/delete/<str:pk>",
        ConfirmDeleteCitationView.as_view(),
        name="delete_citation",
    ),
    path("institution/<str:pk>", InstitutionView.as_view(), name="institution"),
    path("funding/<str:pk>", FundingStreamView.as_view(), name="funding"),
    path("api/", include("rest_framework.urls")),
    path("api/institutes/", InstitutionAPIView.as_view()),
    path("api/parties/", PartyAPIView.as_view()),
    path("api/party/<str:pk>", SpecificPartyAPIView.as_view()),
    path("api/fundings/", FundingStreamAPIView.as_view()),
    path("api/citations/", CitationAPIView.as_view(), name="citations_api"),
    path("api/citation/<str:pk>", SpecificCitationAPIView.as_view(), name='citation_api'),
    path("reviewer_request/", ReviewerRequestView.as_view(), name="reviewer_request"),
]
