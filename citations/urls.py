from django.contrib import admin
from django.urls import path, include
from citations.views import (
    IntroView,
    PartyView,
    CitationView,
    CitationsView,
    PartiesView,
    InstitutionAPIView,
    PartyAPIView,
    SpecificPartyAPIView,
    FundingStreamAPIView,
    CitationAPIView,
    SpecificCitationAPIView,
    NewCitationFormView,
)

app_name = 'citations'
urlpatterns = [
    path('', IntroView.as_view(), name='intro'),
    path('parties/', PartiesView.as_view(), name='parties'),
    path('party/<str:pk>', PartyView.as_view(), name='party'),
    path('citations/',CitationsView.as_view(), name='citations'),
    path('citation/<str:pk>', CitationView.as_view(), name='citation'),
    path('citations/add', NewCitationFormView.as_view(), name='new_citation'),
    path('api/', include('rest_framework.urls')),
    path('api/institutes/', InstitutionAPIView.as_view()),
    path('api/parties/', PartyAPIView.as_view()),
    path('api/party/<str:pk>', SpecificPartyAPIView.as_view()),
    path('api/fundings/', FundingStreamAPIView.as_view()),
    path('api/citations/', CitationAPIView.as_view(), name='citation_api'),
    path('api/citation/<str:pk>', SpecificCitationAPIView.as_view()),
    #path('/'), # Search
    #path('/<id>') # Specific Citation
    #path('/authors') # List all authors alphabetically by last name
    #path('/authors/<id>') # Specific author entry
]