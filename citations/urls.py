from django.contrib import admin
from django.urls import path, include
from citations.views import (
    IntroView,
    PartyView,
    CitationView,
    ConfirmDeleteCitationView,
    InstitutionView,
    FundingStreamView,
    CitationsView,
    PartiesView,
    InstitutionsView,
    FundingStreamsView,
    InstitutionAPIView,
    PartyAPIView,
    SpecificPartyAPIView,
    FundingStreamAPIView,
    CitationAPIView,
    SpecificCitationAPIView,
    NewCitationFormView,
    EditCitationFormView,
)

app_name = 'citations'
urlpatterns = [
    path('', IntroView.as_view(), name='intro'),
    path('parties/', PartiesView.as_view(), name='parties'),
    path('citations/',CitationsView.as_view(), name='citations'),
    path('institutions/',InstitutionsView.as_view(), name='institutions'),
    path('fundingstreams/',FundingStreamsView.as_view(), name='funders'),
    path('party/<str:pk>', PartyView.as_view(), name='party'),
    path('citation/<str:title>', CitationView.as_view(), name='citation'),
    path('citations/add', NewCitationFormView.as_view(), name='add_citation'),
    path('citation/edit/<str:title>', EditCitationFormView.as_view(), name='edit_citation'),
    path('citation/delete/<str:pk>', ConfirmDeleteCitationView.as_view(), name='delete_citation'),
    path('institution/<str:pk>', InstitutionView.as_view(), name='institution'),
    path('funding/<str:pk>', FundingStreamView.as_view(), name='funding'),
    path('api/', include('rest_framework.urls')),
    path('api/institutes/', InstitutionAPIView.as_view()),
    path('api/parties/', PartyAPIView.as_view()),
    path('api/party/<str:pk>', SpecificPartyAPIView.as_view()),
    path('api/fundings/', FundingStreamAPIView.as_view()),
    path('api/citations/', CitationAPIView.as_view(), name='citation_ap'),
    path('api/citation/<str:pk>', SpecificCitationAPIView.as_view()),
    #path('/authors') # List all authors alphabetically by last name
    #path('/authors/<id>') # Specific author entry
]