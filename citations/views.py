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
from django.core.exceptions import PermissionDenied

def fullname(party):
    if party.get('middle_names'):
        if party['middle_names'] != '':
            return f"{party['first_name']} {party['middle_names']} {party['last_name']}"
        
    return f"{party['first_name']} {party['last_name']}"

def deep_search(queryset, term, all_versions):
    q = Q()
    model = queryset.model

    for field in model._meta.get_fields():
        if isinstance(field, (CharField, TextField)):
            q |= Q(**{f"{field.name}__icontains": term})

        elif isinstance(field, ForeignKey):
            related = field.name
            q |= Q(**{f"{related}__{field.target_field.name}__icontains": term})

    return filter_versions(model, queryset.filter(q), all_versions)

def filter_versions(model, queryset, all_versions):

    if all_versions:
        return queryset.all().order_by('-version')

    titles = list(set(queryset.values_list('title', flat=True).distinct()))
    instances = []
    for t in titles:
        instances.append(
            queryset.filter(title=t).order_by('version').last()
        )
    return instances

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
    model = Citations

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        show_all_versions=False
        if self.request.GET.get('legacy_versions','') != '':
            context['all_versions'] = True
            show_all_versions=True

        if self.request.GET.get('search','') != '':
            term = self.request.GET.get('search')
            search_citations = deep_search(self.model.objects.all().order_by('-version'),term, show_all_versions)
            context['search_term'] = term
        else:
            search_citations = filter_versions(self.model, self.model.objects, show_all_versions)

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
            citation = Citations.objects.get(title=title, version=vn)
            citation_data = CitationSerializer(citation).data
        else:
            citation = Citations.objects.filter(title=title).order_by('version').last()
            citation_data = CitationSerializer(citation).data

        latest_version = Citations.objects.filter(title=title).order_by('version').last().version

        context['editable'] = citation.editable
        if citation.version != latest_version:
            context['latest_version'] = latest_version

        context['citation'] = citation_data
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
    
class CitationFormMixin(GenericRenderedView, FormView):

    template_name = "edit_citation.html"
    form_class = CitationForm
    model = Citations

class NewCitationFormView(CitationFormMixin):
    
    def form_valid(self, form):
        return super().form_valid(form)
    
class EditCitationFormView(CitationFormMixin):

    # Needs to pre-populate form with existing values

    # Also adds context to either edit the existing record on form submission
    # Or creates a new record with the given data

    def get_initial(self):
        title = self.kwargs['title']
        if self.model.objects.filter(id=title):
            # Editing existing editable record
            citation = self.model.objects.get(id=title)
            citation_data = CitationSerializer(citation).data
        elif self.model.objects.filter(title=title):
            # Creating a new version (from the latest version)
            citation = Citations.objects.filter(title=title).order_by('version').last()
            citation_data = CitationSerializer(citation).data
            
            # On creating a new version, remove the existing DOI but keep everything
            # else the same
            citation_data.pop('doi_url')

        initial = super().get_initial() | citation_data
        return initial

    def get_context_data(self, title, **kwargs):
        context = super().get_context_data(**kwargs)

        version_update, version_increment = False, False
        if self.model.objects.filter(id=title):
            # Editing existing editable record
            version_update = True
            citation = self.model.objects.get(id=title)
        elif self.model.objects.filter(title=title):
            version_increment = True
            citation = Citations.objects.filter(title=title).order_by('version').last()
            
        if version_update and citation.editable:
            # Allow update of a specific version as it is editable.
            context['on_submit'] = 'update'
        elif version_increment:
            # Creating a new version (from the latest version)
            context['on_submit'] = 'create'
            context['new_version'] = len(self.model.objects.filter(title=title)) + 1
        else:
            # Attempted to access the update view for a specific non-editable version
            # Only allowed if the specific version is the latest?
            if citation.version == Citations.objects.filter(title=citation.title).order_by('version').last():
                context['on_submit'] = 'create'
                context['new_version'] = citation.version + 1
            else:
                raise PermissionDenied(
                    f'Unable to update version {citation.version} as there are later versions '
                    f'already in existence (latest version: v'
                    f'{Citations.objects.filter(title=citation.title).order_by("version").last().version})'
                )
            
        return context