from citations.models import (
    Institutions,
    Authors,
    FundingStreams,
    Citations
)
from citations.serializers import (
    InstitutionSerializer,
    AuthorSerializer,
    FundingStreamSerializer,
    CitationSerializer
)
from rest_framework import mixins
from rest_framework import generics

class InstitutionView(
    mixins.ListModelMixin, mixins.CreateModelMixin, generics.GenericAPIView
    ):
    """
    List all institutions
    """

    queryset = Institutions.objects.all()
    serializer_class = InstitutionSerializer

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)
    
class AuthorView(
    mixins.ListModelMixin, mixins.CreateModelMixin, generics.GenericAPIView
    ):
    """
    List all authors.
    """

    queryset = Authors.objects.all()
    serializer_class = AuthorSerializer

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)
    
class FundingStreamView(
    mixins.ListModelMixin, mixins.CreateModelMixin, generics.GenericAPIView
    ):
    """
    List all funding streams.
    """

    queryset = FundingStreams.objects.all()
    serializer_class = FundingStreamSerializer

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)
    
class CitationView(
    mixins.ListModelMixin, mixins.CreateModelMixin, generics.GenericAPIView
    ):
    """
    List all funding streams.
    """

    queryset = Citations.objects.all()
    serializer_class = CitationSerializer

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)