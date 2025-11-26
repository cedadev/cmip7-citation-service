from django.contrib import admin
from django.urls import path, include
from citations.views import (
    InstitutionAPIView,
    AuthorAPIView,
    SpecificAuthorAPIView,
    FundingStreamAPIView,
    CitationAPIView
)

urlpatterns = [
    path('api/', include('rest_framework.urls')),
    path('api/institute/', InstitutionAPIView.as_view()),
    path('api/author/', AuthorAPIView.as_view()),
    path('api/author/<str:pk>', SpecificAuthorAPIView.as_view()),
    path('api/funding/', FundingStreamAPIView.as_view()),
    path('api/citation/', CitationAPIView.as_view()),
    #path('/'), # Search
    #path('/<id>') # Specific Citation
    #path('/authors') # List all authors alphabetically by last name
    #path('/authors/<id>') # Specific author entry
]