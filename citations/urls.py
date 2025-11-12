from django.contrib import admin
from django.urls import path, include
from citations.views import (
    InstitutionView,
    AuthorView,
    FundingStreamView,
    CitationView
)

urlpatterns = [
    path('api/', include('rest_framework.urls')),
    path('institute/', InstitutionView.as_view()),
    path('author/', AuthorView.as_view()),
    path('funding/', FundingStreamView.as_view()),
    path('citation/', CitationView.as_view()),
    #path('/'), # Search
    #path('/<id>') # Specific Citation
    #path('/authors') # List all authors alphabetically by last name
    #path('/authors/<id>') # Specific author entry
]