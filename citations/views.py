from citations.models import (
    Institutions,
    Parties,
    FundingStreams,
    Citations
)
from citations.serializers import (
    InstitutionSerializer,
    PartySerializer,
    FundingStreamSerializer,
    CitationSerializer
)

from citations.forms import(
    CitationForm
)

from rest_framework.authentication import TokenAuthentication
from django.core import serializers
from django.shortcuts import redirect
from rest_framework import permissions

from rest_framework import mixins
from rest_framework import generics

from rest_framework.exceptions import APIException

from django.views.generic.base import TemplateView
from django.views.generic.edit import FormView
from django.contrib.sites import shortcuts
from django.http import HttpResponse, HttpResponseForbidden
from django.contrib.auth.mixins import LoginRequiredMixin
from django.conf import settings
from django.db.models import Q, CharField, TextField, ForeignKey

import hashlib

def fullname(party):
    if party.get('middle_names'):
        if party['middle_names'] != '':
            return f"{party['first_name']} {party['middle_names']} {party['last_name']}"
        
    return f"{party['first_name']} {party['last_name']}"

def deep_search(queryset, term):
    q = Q()
    model = queryset.model

    for field in model._meta.get_fields():
        if isinstance(field, (CharField, TextField)):
            q |= Q(**{f"{field.name}__icontains": term})

        elif isinstance(field, ForeignKey):
            related = field.name
            q |= Q(**{f"{related}__{field.target_field.name}__icontains": term})

    return queryset.filter(q)

class GenericRenderedView(TemplateView):

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if settings.USE_CEDA_BRANDING:
            context['template_base'] = 'fwtheme_django/layout.html'
        else:
            context['template_base'] = 'bases/generic_base.html'
        return context

class IntroView(LoginRequiredMixin,GenericRenderedView):
    login_url = settings.LOGIN_URL
    template_name = 'intro.html'

class PartiesView(GenericRenderedView):
    template_name = 'parties.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        parties = []
        for party in Parties.objects.all():
            parties.append(PartySerializer(party).data)
        context['parties'] = parties
        return context
    
class CitationsView(GenericRenderedView):
    template_name = 'citations.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.request.GET.get('search','') != '':
            term = self.request.GET.get('search')
            search_citations = deep_search(Citations.objects.all(),term)
            context['search_term'] = term
        else:
            search_citations = Citations.objects.all()

        citations = []
        for citation in search_citations:
            cite = CitationSerializer(citation).data
            cite['primary'] = {
                'fullname':fullname(cite['primary']),
                'id':cite['primary']['id']
            }
            cite['version'] = citation.version
            citations.append(cite)
        context['citations'] = citations
        return context
    
class CitationView(GenericRenderedView):
    template_name = 'citation.html'

    def get_context_data(self, title, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.request.GET.get('version'):
            vn = self.request.GET.get('version')
            citation = CitationSerializer(Citations.objects.get(title=title, version=vn)).data
        else:
            citations = Citations.objects.filter(title=title).order_by('version')
            print(citations)
            citation = CitationSerializer(citations.last()).data
        context['citation'] = citation
        return context
    
class PartyView(GenericRenderedView):
    template_name = 'party.html'

    def get_context_data(self, pk, **kwargs):
        context = super().get_context_data(**kwargs)
        instance = Parties.objects.get(id=pk)
        context['party'] = PartySerializer(instance).data

        primary_citations = [{
            'name': citation.title,
            'id': citation.id
        } for citation in Citations.objects.filter(primary=instance)]
        context['primaries'] = primary_citations
        contact_citations = [{
            'name': citation.title,
            'id': citation.id
        } for citation in Citations.objects.filter(contacts=instance)]
        context['contacts'] = contact_citations

        return context

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
    model = Institutions
    queryset = Institutions.objects.all()
    serializer_class = InstitutionSerializer

class SpecificPartyAPIView(SpecificAPIView):
    """
    Action requests related to Specific Party
    """

    model = Parties
    queryset = Parties.objects.all()
    serializer_class = PartySerializer
    
class PartyAPIView(GenericAPIView):
    """
    List all parties.
    """
    model = Parties
    queryset = Parties.objects.all()
    serializer_class = PartySerializer
    
class FundingStreamAPIView(GenericAPIView):
    """
    List all funding streams.
    """
    model = FundingStreams
    queryset = FundingStreams.objects.all()
    serializer_class = FundingStreamSerializer
    
class CitationAPIView(GenericAPIView):
    """
    List all funding streams.
    """
    model = Citations
    queryset = Citations.objects.all()
    serializer_class = CitationSerializer

class SpecificCitationAPIView(SpecificAPIView):
    """
    List all funding streams.
    """
    model = Citations
    queryset = Citations.objects.all()
    serializer_class = CitationSerializer

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if not instance.editable:
            return HttpResponseForbidden(
                f'Editing the record {instance.id} is forbidden'
            )

        return super().update(request, *args, **kwargs)

class NewCitationFormView(FormView):

    template_name = "new_citation.html"
    form_class = CitationForm
    
    def form_valid(self, form):
        return super().form_valid(form)