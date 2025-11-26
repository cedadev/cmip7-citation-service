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

from rest_framework.authentication import TokenAuthentication
from rest_framework import permissions

from rest_framework import mixins
from rest_framework import generics

from rest_framework.exceptions import APIException

class GenericAPIView(
    mixins.ListModelMixin, mixins.CreateModelMixin, generics.GenericAPIView
    ):
    """
    Generic Method Additions to the API View
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        if self.request.method == 'GET' or self.request.method == 'OPTIONS':
            return [permissions.AllowAny()]
        else:
            # Post or otherwise
            return [permissions.IsAuthenticated()]
        
    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)
    
class SpecificAPIView(
    mixins.CreateModelMixin, mixins.RetrieveModelMixin, 
    mixins.UpdateModelMixin, generics.GenericAPIView):
    """
    Specific View Methods
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        if self.request.method == 'GET' or self.request.method == 'OPTIONS':
            return [permissions.AllowAny()]
        else:
            # Post or otherwise
            return [permissions.IsAuthenticated()]
        
    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)
    
    def put(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

class InstitutionAPIView(GenericAPIView):
    """
    List all institutions
    """

    queryset = Institutions.objects.all()
    serializer_class = InstitutionSerializer

class SpecificAuthorAPIView(SpecificAPIView):
    """
    Action requests related to Specific Author
    """

    queryset = Authors.objects.all()
    serializer_class = AuthorSerializer
    
class AuthorAPIView(GenericAPIView):
    """
    List all authors.
    """

    queryset = Authors.objects.all()
    serializer_class = AuthorSerializer
    
class FundingStreamAPIView(GenericAPIView):
    """
    List all funding streams.
    """

    queryset = FundingStreams.objects.all()
    serializer_class = FundingStreamSerializer
    
class CitationAPIView(GenericAPIView):
    """
    List all funding streams.
    """

    queryset = Citations.objects.all()
    serializer_class = CitationSerializer
