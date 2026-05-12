import copy
import json
import ast

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import (LoginRequiredMixin,
                                        PermissionRequiredMixin)
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import CharField, ForeignKey, Q, TextField
from django.db.models.functions import Lower
from django.http import (HttpResponseForbidden, HttpResponseNotFound,
                         HttpResponseRedirect)
from django.urls import reverse
from django.views.generic.base import TemplateView
from django.views.generic.edit import FormView
from rest_framework import generics, mixins, permissions, status
from rest_framework.authentication import TokenAuthentication
from rest_framework.response import Response
from slack_sdk import WebClient

from citations.consumer.write import delete_instance
from citations.external import resolve_drs
from citations.forms import (ContactFormSet, EditCitationForm, FunderFormSet,
                             InstitutionFormSet, InstitutionIdForm,
                             NewCitationForm, ReferenceFormSet, ReplicaFormSet,
                             reference_options, reference_mapping)
from citations.models import (Citations, FundingStreams, Institutions, Parties,
                              References)
from citations.serializers import (CitationsSerializer,
                                   FundingStreamsSerializer,
                                   InstitutionsSerializer, PartiesSerializer,
                                   ReferencesSerializer, chain_new_objects,
                                   handle_update, title_from_facets)
from typing import Union
from citations.utils import LABEL_MAPPINGS, CORE_FACETS

def create_new_permission(user, institution_id: str):

    content_type_citation = ContentType.objects.get_for_model(Citations)

    if not Permission.objects.filter(codename=f'edit_{institution_id}').exists():
        pm = Permission.objects.create(
            codename=f'edit_{institution_id}', 
            name=f'Can edit {institution_id} citations',
            content_type=content_type_citation)
        
        user.user_permissions.add(pm)
        user.save()


def get_citable_party(party: Parties):
    if party.middle_names:
        return f'{party.last_name}, {party.first_name} {party.middle_names}'
    else:
        return f'{party.last_name}, {party.first_name}'
    
def get_drs_url(citation_data: dict) -> Union[str,None]:

    if not hasattr(settings, 'METAGRID_URL'):
        return None
    
    for facet in CORE_FACETS:
        if not bool(citation_data.get(facet,False)):
            return None

    if citation_data.get('domain_id') is not None:
        return "%2C".join([
            f'{settings.METAGRID_URL}/search?project={citation_data["mip_era"]}+STAC&activeFacets=%7B"mip_era"%3A"{citation_data["mip_era"]}"',
            f'"institution_id"%3A"{citation_data["institution_id"]}"',
            f'"activity_id"%3A"{citation_data["activity_id"]}"',
            f'"source_id"%3A"{citation_data["source_id"]}"',
            f'"driving_experiment_id"%3A"{citation_data["experiment_id"]}"',
            f'"domain_id"%3A"{citation_data["domain_id"]}'
        ])
    else:
        return "%2C".join([
            f'{settings.METAGRID_URL}/search?project={citation_data["mip_era"]}+STAC&activeFacets=%7B"mip_era"%3A"{citation_data["mip_era"]}"',
            f'"institution_id"%3A"{citation_data["institution_id"]}"',
            f'"activity_id"%3A"{citation_data["activity_id"]}"',
            f'"source_id"%3A"{citation_data["source_id"]}"',
            f'"experiment_id"%3A"{citation_data["experiment_id"]}"'
        ])
    
def get_code_snippet(citation_data: dict) -> Union[str,None]:

    if not hasattr(settings, 'STAC_API'):
        return None
    
    for facet in CORE_FACETS:
        if citation_data.get(facet,None) is None:
            return None

    query = [
        f'      "cmip7:mip_era={citation_data["mip_era"]}",',
        f'      "cmip7:activity_id={citation_data["activity_id"]}",',
    ]

    if citation_data.get('domain_id') is not None:
        query += [
            f'      "cmip7:domain_id={citation_data["domain_id"]}",',
            f'      "cmip7:institution_id={citation_data["institution_id"]}",',
            f'      "cmip7:driving_experiment_id={citation_data["experiment_id"]}",',
            f'      "cmip7:source_id={citation_data["source_id"]}",',
        ]
    else:
        query += [
            f'      "cmip7:institution_id={citation_data["institution_id"]}",',
            f'      "cmip7:source_id={citation_data["source_id"]}",',
            f'      "cmip7:experiment_id={citation_data["experiment_id"]}",',
        ]

    code_snippet = [
        'from pystac.client import Client',
        '',
        f'cli = Client.open("{settings.STAC_API}")',
        'cli.search(',
        '   collections=["cmip7"],',
        '   query=['
    ] + query + [
        '])'
    ]

    return "\n".join(code_snippet)

def get_cite_as(citation: Citations):
    primary = get_citable_party(citation.primary) + '; '

    return {
        'title': f'{citation.title} ({getattr(citation,"publication_year", "2026")})',
        'rotc': primary + '; '.join([
            get_citable_party(contact)
            for contact in citation.contacts.all()
        ])
    }

def render_abstract(data: dict) -> str:

    replace_refs = {}
    for bracket in data['abstract'].split('('):

        try:
            partial_ref = bracket.split(')')[0]
            name = partial_ref.split(' ')[0]
            year = partial_ref.split(' ')[-1]
            for reftype in CitationsSerializer.Meta.citation_types:
                for ref in data.get(reftype,[]):
                    if name in ref['title'] and year in ref['title']:
                        replace_refs[f'({partial_ref})'] = ''.join([
                            '<a href="',ref['id'],
                            '">(',partial_ref,')</a>'
                        ])
        except IndexError:
            pass

    abstract = data['abstract']
    for k,v in replace_refs.items():
        abstract = abstract.replace(k,v)

    return str(abstract)

def render_rights(data: dict) -> str:

    if data.get('rights') in settings.RIGHTS_MAP:
        return f'<a href={settings.RIGHTS_MAP[data["rights"]][0]}>' + \
            f'{settings.RIGHTS_MAP[data["rights"]][1]} ({data["rights"]})</a>'
    return data.get('rights')


def render_reference_html(ref: dict) -> dict:

    if ref['title'][-1] != '.':
        ref['title'] += '.'

    ref['citeas'] = ref['citeas'].replace(
        ref["title"],f"<b>{ref["title"]} </b>").replace(
            ref["id"],f"<a href={ref['id']}>{ref['id']}.</a>")

    return ref

def fullname(party):
    if party.get('middle_names'):
        if party['middle_names'] != '':
            return f"{party['first_name']} {party['middle_names']} {party['last_name']}"
        
    return f"{party['first_name']} {party['last_name']}"

def deep_search(queryset, term: str, order_by: str, all_versions=True):
    q = Q()
    model = queryset.model

    for field in model._meta.get_fields():
        if isinstance(field, (CharField, TextField)):
            q |= Q(**{f"{field.name}__icontains": term})

        elif isinstance(field, ForeignKey):
            related = field.name
            q |= Q(**{f"{related}__{field.target_field.name}__icontains": term})

    if not all_versions:
        return filter_versions(queryset.filter(q))
    else:
        return queryset.filter(q).order_by(order_by)

def filter_versions(queryset):

    titles = list(set(queryset.values_list('title', flat=True).distinct()))
    instances = []
    for t in sorted(titles):
        instances.append(
            queryset.filter(title=t).order_by('version').last()
        )
    return instances

def unwrap_request(data: dict) -> dict:
    return {k:v for k,v in data.items()}

def check_publish_ok(request, data: dict):

    status = True
    if not data.get('doi_url'):
        if not resolve_drs(data.get('drs_url', get_drs_url(data))):
            messages.error(request, "Failed to resolve DRS URL. DOI cannot be minted until data is available.")
        else:
            messages.error(request, f"Failed to mint DOI for the record {data['title']} (v{data['version']})")
        status = False
        data = {'warnings': 'publication unsuccessful'} | data
    else:
        messages.success(request, f"DOI '{data['doi_url']}' ({data['publication_year']}) minted.")

    return data, status

class GenericRenderedView(TemplateView):

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if settings.USE_CEDA_BRANDING:
            context['template_base'] = 'fwtheme_django/layout.html'
        else:
            context['template_base'] = 'bases/generic_base.html'

        return context
    
    def get_instance(self, pk):
        return self.serializer_class(self.model.objects.get(pk=pk)).data
    
class PaginatedListView(GenericRenderedView):

    def get_pagination(self, search_queryset, page_number: int = 1):
        paginator = Paginator(search_queryset, self.paginate_by)
        return paginator.get_page(page_number)
    
    def get_context_data(self, page_obj, page_number: int = 1, search_term = None, count=None,**kwargs):
        context = super().get_context_data(**kwargs)

        context['total_results'] = count or self.model.objects.count()
        context['pagination'] = min(self.paginate_by * page_number, int(context['total_results']))
        context[self.model._meta.model_name] = page_obj
        if search_term is not None:
            context['search_term'] = search_term

        return context
    
    def perform_search(self) -> tuple:
        count = self.model.objects.count()
        term = None
        if self.request.GET.get('search') != '' and self.request.GET.get('search') is not None:
            term = self.request.GET.get('search')
            searches = deep_search(self.model.objects.all(),term, order_by=self.order_by)
        else:
            searches = self.model.objects.all().order_by(self.order_by)
            count = len(searches)
        return searches, count, term

    def get(self, request, *args, **kwargs):
        """
        Get list view with filtering"""
        searches, count, term = self.perform_search()

        adj_searches          = self.adjust_for_UI_render(searches)

        # Pagination
        self.page_number = int(request.GET.get("page", 1))
        page_obj    = self.get_pagination(adj_searches, self.page_number)

        context = self.get_context_data(page_obj=page_obj, search_term=term, page_number=self.page_number, count=count)

        # HTMX request - return only the rows fragment
        if request.headers.get("HX-Request") == "true":
            from django.template.response import TemplateResponse
            return TemplateResponse(
                request=self.request,
                template=self.partial_template,
                context=context,
            )

        # Normal full-page load
        return self.render_to_response(context)

    def adjust_for_UI_render(self, queryset) -> list:
        return [self.serializer_class(q).data for q in queryset]

class GenericAPIView(
        mixins.ListModelMixin, 
        mixins.CreateModelMixin, 
        generics.GenericAPIView
    ):
    """
    Generic Method Additions to the API View
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    json_fields = []

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
    
    def create(self, request, *args, **kwargs):
        data=unwrap_request(request.data)
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user_id=request.user.username)

        return Response(serializer.validated_data, status=status.HTTP_201_CREATED)
    
    def initialize_request(self, request, *args, **kwargs):
        """
        Decode Information Given to POST requests
        """
        req = super().initialize_request(request, *args, **kwargs)

        # Modify req.data here
        mutable = req.data.copy()
        for field in self.json_fields:
            if mutable.get(field,'') != '' and isinstance(mutable.get(field),str):
                try:
                    mutable[field] = json.loads(mutable[field])
                except json.decoder.JSONDecodeError:
                    mutable[field] = json.loads(mutable[field].replace("'",'"'))
        req._full_data = mutable  # override parsed data

        return req
    
class SpecificAPIView(
    mixins.CreateModelMixin, mixins.RetrieveModelMixin, 
    mixins.UpdateModelMixin, generics.GenericAPIView,
    mixins.DestroyModelMixin):
    """
    Specific View Methods
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    json_fields = []

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
    
    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        delete_instance(
            update_handler=handle_update,
            model=self.model,
            user=request.user.username,
            id=instance.id)
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    def update(self, request, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save(user_id=request.user.username)

        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)
    
    def initialize_request(self, request, *args, **kwargs):
        """
        Decode Information Given to POST requests
        """
        req = super().initialize_request(request, *args, **kwargs)

        # Modify req.data here
        mutable = req.data.copy()
        for field in self.json_fields:
            if mutable.get(field,'') != '' and isinstance(mutable.get(field),str):
                mutable[field] = json.loads(mutable[field])[0]
        req._full_data = mutable  # override parsed data

        return req
    
class PartiesView(PaginatedListView):
    template_name = 'parties.html'
    partial_template = 'partials/parties_partial.html'
    model = Parties
    serializer_class = PartiesSerializer
    paginate_by = 10
    order_by = 'last_name'
    
class InstitutionsView(PaginatedListView):
    template_name = 'institutions.html'
    partial_template = 'partials/institutions_partial.html'
    model = Institutions
    serializer_class = InstitutionsSerializer
    paginate_by = 10
    order_by = Lower('name')

class FundingStreamsView(PaginatedListView):
    template_name = 'streams.html'
    partial_template = 'partials/streams_partial.html'
    model = FundingStreams
    serializer_class = FundingStreamsSerializer
    paginate_by = 10
    order_by = Lower('name')

    def adjust_for_UI_render(self, queryset) -> list:
        adj_queryset = []
        for q in queryset:
            serial = self.serializer_class(q).data
            serial['affiliation_id'] = q.affiliation_id
            adj_queryset.append(serial)
        return adj_queryset

class CitationsView(PaginatedListView):
    template_name = 'citations.html'
    partial_template = 'partials/citations_partial.html'
    model = Citations
    serializer_class = CitationsSerializer
    paginate_by = 10
    order_by = '-version,title'

    def get_context_data(self, *args,**kwargs):
        context = super().get_context_data(*args, **kwargs)
        context['all_versions'] = bool(self.request.GET.get('legacy_versions','') != '')
        return context
    
    def perform_search(self, show_all_versions: bool = False) -> tuple:
        count = self.model.objects.count()
        show_all_versions = bool(self.request.GET.get('legacy_versions','') != '')
        term = None
        if self.request.GET.get('search') != '' and self.request.GET.get('search') is not None:
            term = self.request.GET.get('search')
            search_citations = deep_search(self.model.objects.all(),term, order_by=self.order_by
                                           , all_versions=show_all_versions)
        else:
            if show_all_versions:
                search_citations = self.model.objects.all().order_by(self.order_by)
                count = len(search_citations)
            else:
                search_citations = filter_versions(self.model.objects)
                count = len(search_citations)
        return search_citations, count, term
    
    def adjust_for_UI_render(self, queryset) -> list:
        # Adjustments for UI rendering
        citations = []
        for citation in queryset:
            cite = self.serializer_class(citation).data
            cite['primary'] = {
                'fullname':fullname(cite['primary']),
                'id':cite['primary']['id']
            }
            cite['version'] = citation.version
            citations.append(cite)
        return citations
    
class CitationView(GenericRenderedView):
    template_name = 'citation.html'

    def get_context_data(self, title, **kwargs):
        context = super().get_context_data(**kwargs)

        if not Citations.objects.filter(title=title):
            raise HttpResponseNotFound('The requested citation title does not yet exist.')

        if self.request.GET.get('version'):
            vn = self.request.GET.get('version')
            citation = Citations.objects.get(title=title, version=vn)
            citation_data = CitationsSerializer(citation).data
        else:
            citation = Citations.objects.filter(title=title).order_by('version').last()
            citation_data = CitationsSerializer(citation).data

        latest_version = Citations.objects.filter(title=title).order_by('version').last().version

        reviewer = self.request.user
        if reviewer.has_perm('citations.add_citations'):
            context['is_reviewer'] = True

        # Invisible properties
        context['editable'] = citation.editable
        context['published'] = citation.published

        if citation.version != latest_version:
            context['latest_version'] = latest_version


        ## View-specific rendering
        
        # 1. Render cite_as property
        if citation.published:
            context['cite_as'] = get_cite_as(citation)

        # 2. Render References
        for reference_type in CitationsSerializer.Meta.citation_types:
            if citation_data.get(reference_type):
                for ref in citation_data[reference_type]:
                    ref = render_reference_html(ref)

        # 3. Add Code Snippet
        context['code_snippet'] = get_code_snippet(citation_data)

        # 4. Add Data Access URL (DRS_URL)
        if not bool(citation.drs_url):
            context['drs_url'] = get_drs_url(citation_data)
        else:
            context['drs_url'] = citation.drs_url

        # 5. Render Rights
        context['rights'] = render_rights(citation_data)

        # 6. Render Abstract
        context['abstract'] = render_abstract(citation_data)

        context['citation'] = citation_data
        return context
    
class InstitutionView(GenericRenderedView):
    template_name = 'institution.html'

    model = Institutions
    serializer_class = InstitutionsSerializer

    def get_context_data(self, pk, **kwargs):
        context = super().get_context_data(**kwargs)
        context['institute'] = self.get_instance(pk=pk)

        context['funding_contribs'] = [n for n in FundingStreams.objects.filter(affiliation=pk)]

        context['citations'] = (Citations.objects.filter(institutions__id=pk).values_list('title', flat=True).distinct())

        return context
    
class FundingStreamView(GenericRenderedView):
    template_name = 'fundingstream.html'

    model = FundingStreams
    serializer_class = FundingStreamsSerializer

    def get_context_data(self, pk, **kwargs):
        context = super().get_context_data(**kwargs)
        context['stream'] = self.get_instance(pk=pk)
        context['stream']['affiliation_id'] = self.model.objects.get(pk=pk).affiliation.id

        context['citations'] = (Citations.objects.filter(funders__id=pk).values_list('title', flat=True).distinct())

        return context

class PartyView(GenericRenderedView):
    template_name = 'party.html'

    def get_context_data(self, pk, **kwargs):
        context = super().get_context_data(**kwargs)
        instance = Parties.objects.get(id=pk)
        context['party'] = PartiesSerializer(instance).data

        primary_citations = [{
            'title': citation.title,
            'version':citation.version,
            'id': citation.id
        } for citation in Citations.objects.filter(primary=instance)]
        context['primaries'] = primary_citations
        contact_citations = [{
            'title': citation.title,
            'version':citation.version,
            'id': citation.id
        } for citation in Citations.objects.filter(contacts=instance)]
        context['contacts'] = contact_citations

        return context

class InstitutionAPIView(GenericAPIView):
    """
    List all institutions
    """
    model = Institutions
    queryset = Institutions.objects.all()
    serializer_class = InstitutionsSerializer

class SpecificPartyAPIView(SpecificAPIView):
    """
    Action requests related to Specific Party
    """

    model = Parties
    queryset = Parties.objects.all()
    serializer_class = PartiesSerializer
    
class PartyAPIView(GenericAPIView):
    """
    List all parties.
    """
    model = Parties
    queryset = Parties.objects.all()
    serializer_class = PartiesSerializer
    
class FundingStreamAPIView(GenericAPIView):
    """
    List all funding streams.
    """
    model = FundingStreams
    queryset = FundingStreams.objects.all()
    serializer_class = FundingStreamsSerializer
    
class CitationAPIView(GenericAPIView):
    """
    List all funding streams.
    """
    model = Citations
    queryset = Citations.objects.all()
    serializer_class = CitationsSerializer
    json_fields = ['primary','funders','institutions','contacts', 'is_cited_by', 'is_referenced_by','cites']

    def create(self, request, *args, **kwargs):
        data = unwrap_request(request.data)

        publish = data.pop('publish_on_save',None)

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        title = serializer.validated_data.get('title')
        if not title:
            title = title_from_facets(serializer.validated_data)

        if 'version' in request.data:
            version = request.data['version']
        else:
            version = None
            inst = self.model.objects.filter(title=title).order_by('-version')
            if inst:
                version = inst.last().version

        latest = self.model.objects.filter(title=title, version=version)
        if latest:
            if not latest[0].editable:
                return Response(serializer.validated_data, status=status.HTTP_405_METHOD_NOT_ALLOWED)

        if 'institution_id' in serializer.validated_data: 
            create_new_permission(request.user, serializer.validated_data['institution_id'])
            
        data = serializer.save(publish=publish, user_id=request.user.username)
        if publish:
            data, _ = check_publish_ok(request, data)
        return Response(data, status=status.HTTP_201_CREATED)

class SpecificCitationAPIView(SpecificAPIView):
    """
    List all funding streams.
    """
    model = Citations
    queryset = Citations.objects.all()
    serializer_class = CitationsSerializer

    json_fields = ['primary','funders','institutions','contacts', 'is_cited_by','is_referenced_by', 'cites']

    def update(self, request, *args, **kwargs):
        data = unwrap_request(request.data)
        instance = self.get_object()
        if not instance.editable:
            return HttpResponseForbidden(
                f'Editing the record {instance.id} is forbidden'
            )
        
        publish = data.pop('publish_on_save',None)
        
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)

        data = serializer.save(publish=publish, user_id=request.user.username)
        if publish:
            data, _ = check_publish_ok(request, data)

        return Response(data, status=status.HTTP_201_CREATED)
    
    def get(self, request, *args, **kwargs):

        # Determine ID here
        pk = kwargs['pk']
        if self.model.objects.filter(title=pk):
            self.kwargs['pk'] = self.model.objects.filter(title=pk).order_by('-version').last().pk

        return self.retrieve(request, *args, **kwargs)
    
    def put(self, request, *args, **kwargs):

        # Determine ID here
        pk = kwargs['pk']
        if self.model.objects.filter(title=pk):
            self.kwargs['pk'] = self.model.objects.filter(title=pk).order_by('-version').last().pk
            
        return self.update(request, *args, **kwargs)
    
def check_changes(instance, data):
    changed_data = {}
    for attr, value in data.items():
        if str(value) != str(getattr(instance, attr, None)):
            changed_data[attr] = value
    return changed_data

class CitationFormMixin(PermissionRequiredMixin, GenericRenderedView, FormView):

    permission_required='citations.add_citations'
    raise_exception=True
    template_name = "edit_citation.html"
    model = Citations
    serializer_class = CitationsSerializer

    def redirect_on_success(self, title: str = None, status: bool = True):
        
        args = [title]
        msg = 'Your citation updates have been submitted and will appear here when they have been processed.'
        
        if title is None:
            args = None
            msg = 'Your citations have been submitted and will appear here when they have been processed.'

        if not status:
            messages.error(self.request, 'DOI Minting has not been completed. The record will remain unpublished until the above issue is resolved.')

        messages.success(self.request, msg)

        return HttpResponseRedirect(reverse('citations:citation', args=args))
    
    def initial_formset_values(self, context) -> dict:
        context['contact_formset'] = ContactFormSet()
        context['institution_formset'] = InstitutionFormSet()
        context['funder_formset'] = FunderFormSet()
        context['replica_formset'] = ReplicaFormSet()
        context['reference_formset'] = ReferenceFormSet()
        return context

    def new_version(self, **kwargs):
        if self.request.GET.get('title'):
            # Create from Previous
            new_version = Citations.objects.filter(title=self.request.GET.get('title')).order_by('version').last().version + 1
        elif self.kwargs.get('title'):
            # Edit Current
            new_version = Citations.objects.filter(title=self.kwargs.get('title')).order_by('version').last().version
        else:
            # Create New
            new_version = 1
        return new_version
    
    def dispatch(self, request, *args, **kwargs):
        """
        Setup for form view
        """
        if not request.user.user_permissions.filter(codename='add_citations'):
            return HttpResponseRedirect(reverse('citations:reviewer_request'))

        title = kwargs.get('title') or request.GET.get('title')
        if title:
            institute = self.model.objects.filter(title=title).order_by('-version').last().institution_id
            if institute:
                if not request.user.user_permissions.filter(codename=f'edit_{institute}'):
                    return HttpResponseRedirect(reverse('citations:reviewer_request'))
                
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, title: str = None, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.request.POST:
            context['contact_formset'] = ContactFormSet(self.request.POST)
            context['institution_formset'] = InstitutionFormSet(self.request.POST)
            context['funder_formset'] = FunderFormSet(self.request.POST)
            context['replica_formset'] = ReplicaFormSet(self.request.POST)
            context['reference_formset'] = ReferenceFormSet(self.request.POST)
        else:
            context = self.initial_formset_values(context)

        context['on_submit'] = self.on_submit
        
        context['new_version'] = self.new_version(title=title)

        required_fields = []
        for serializer in [
            InstitutionsSerializer,
            PartiesSerializer,
            FundingStreamsSerializer,
            CitationsSerializer,
            ReferencesSerializer,
        ]:
            required_fields += [
                f[0].upper() + f[1:].replace('_',' ') for f in serializer.Meta.required_fields
            ]

        context['required_fields'] = list(set(required_fields))
        context['publishable'] = True
        return context

    def clean_formset_data(self, formset: dict, serializer, model, allow_update: bool = False) -> list:
        """
        Clean data from a formset and determine if updates are required
        """
        pks = []
        for fd in formset:

            if not fd:
                continue
            formdata = dict(getattr(fd,'cleaned_data',{}))
            if not formdata:
                continue

            filter_kwargs = {k:v for k,v in formdata.items() if k in serializer.Meta.required_fields}
            inst = model.objects.filter(**filter_kwargs)
            
            if inst:
                inst = inst[0]
                changed_data = check_changes(inst, formdata)
                inst_pk = inst.pk
            else:
                changed_data = formdata

            if changed_data:
                inst_pk = chain_new_objects(
                    data=changed_data | filter_kwargs,
                    serializer=serializer,
                    model=model,
                    filter_kwargs=serializer.Meta.required_fields,
                    allow_update=allow_update) # Allowed updates from citation form directly to contacts
            pks.append(inst_pk)
        return pks
    
    def process_references(self, formset) -> dict:
        ref_data = {}
        ref_data['is_cited_by']      = []
        ref_data['is_referenced_by'] = []
        ref_data['cites']            = []

        for form in formset:

            if not form:
                continue
            formdata = dict(getattr(form,'cleaned_data',{}))
            if not formdata:
                continue
            if len(formdata.keys()) < 3:
                continue

            formdata['id'] = formdata.pop('DOI')
            rel_id = formdata.pop('relation')
            relation = [r[1] for r in reference_options if str(r[0]) == str(rel_id)][0]

            inst = References.objects.filter(id=formdata['id'])
            if inst:
                inst = inst[0]
                changed_data = check_changes(inst, formdata)
                inst_pk = inst.pk
            else:
                changed_data = formdata

            if changed_data:
                inst_pk = chain_new_objects(
                    data=changed_data | {'id':formdata['id']},
                    serializer=ReferencesSerializer,
                    model=References,
                    filter_kwargs=['id'],
                    allow_update=True)
            ref_data[relation].append(inst_pk)
        return ref_data
             
    def create_from_formsets(self, form, **kwargs) -> dict:

        contact_formset     = ContactFormSet(self.request.POST)
        institution_formset = InstitutionFormSet(self.request.POST)
        funder_formset      = FunderFormSet(self.request.POST)
        reference_formset   = ReferenceFormSet(self.request.POST)

        def check_empty_custom(form, nonempty_fields: list) -> bool:
            """
            Allow this form to be empty based on custom logic.

            If a field in the form evaluates to True it is not empty.
            
            Returns True if the form is considered empty for all relevant fields.
            """

            for field, value in form.cleaned_data.items():
                if field in nonempty_fields:
                    continue

                if value:
                    return False
            return True


        errors = 0

        error_map = {}
        for formset in [contact_formset, institution_formset, funder_formset, reference_formset]:
            for form_pt in formset:
                if not form_pt.is_valid() and not form_pt.empty_permitted:

                    if formset == reference_formset:
                        if check_empty_custom(form_pt, nonempty_fields=['relation']):
                            continue
                    err_msgs = []
                    for err, msg in form_pt.errors.items():
                        err_msgs.append(f'{err}: {msg[0]}')
                        errors += 1
                    error_map[formset.prefix] = err_msgs

        if errors > 0:
            return self.render_to_response(self.get_context_data(form=form, **kwargs) | {'extra_errors':error_map, 'errors': errors})
        
        main_data = {}
        main_data['contacts']     = []
        main_data['institutions'] = []
        main_data['funders']      = []
        
        primary_index = int(self.request.POST.get("primary_contact"))
        contacts = self.clean_formset_data(
            contact_formset,
            PartiesSerializer,
            Parties,
            allow_update=True)
         
        for i, contact in enumerate(contacts):   
            if i == primary_index:
                main_data['primary_id'] = contact
            else:
                main_data['contacts'].append(contact)
        
        if main_data.get('primary_id',None) is None:
            return self.render_to_response(
                self.get_context_data(form=form, **kwargs) | {
                    'errors': '1',
                    'extra_errors': {
                        'contact':["A primary contact must be provided"],
                }})

        main_data['institutions'] = self.clean_formset_data(
            institution_formset, InstitutionsSerializer, Institutions)

        main_data['funders'] = self.clean_formset_data(
            funder_formset, FundingStreamsSerializer, FundingStreams
        )

        main_data.update(
            self.process_references(reference_formset)
        )

        return main_data
    
    def clean_replica_data(self, cloned_data, ntitle):

        ndata = copy.deepcopy(cloned_data)
        ndata['title'] = ntitle
        ndata.pop('id',None)

        instance = None
        queryset = self.model.objects.filter(title=ntitle).order_by('-version')
        if queryset:
            instance = queryset[0]
            ndata['id'] = ndata['title'] + '_v' + str(instance.version)
            ndata['version'] = instance.version
        else:
            ndata['id'] = ndata['title'] + '_v1'
            ndata['version'] = 1

        for field in getattr(self.serializer_class.Meta,'non_replicating_fields',[]):
            ndata.pop(field,'')

        return ndata, instance

    def replicate_data(self, instance=None, data=None):

        for v, k in LABEL_MAPPINGS.items():
            data[k] = data.pop(v,None)

        pubstatus = True
        publish = self.request.POST.get('publish')

        serializer = self.serializer_class(
            instance=instance,
            data=data)
            
        serializer.is_valid(raise_exception=True)
        obj = serializer.save(
            publish=publish, 
            user_id=self.request.user.username)

        if publish:
            obj, pubstatus = check_publish_ok(self.request, obj)

        # Determine replicas
        replica_formset = ReplicaFormSet(self.request.POST)
        replicas = []
        for r in replica_formset:
            if r.is_valid():
                if 'title' in r.cleaned_data:
                    replicas.append(r.cleaned_data['title'])

        if 'replicate' in self.request.POST:
            for r in replicas:

                ndata, inst = self.clean_replica_data(serializer.validated_data, r)

                serializer = self.serializer_class(
                    instance=inst,
                    data=ndata)
            
                serializer.is_valid(raise_exception=True)
                obj = serializer.save(
                    publish=publish,
                    user_id=self.request.user.username)

                if publish:
                    obj, pubstatus = check_publish_ok(self.request, obj)

            if len(replicas) > 0:
                return self.redirect_on_success(status=pubstatus)
            
        if 'institution_id' in serializer.validated_data: 
            create_new_permission(self.request.user, serializer.validated_data['institution_id'])
            
        return self.redirect_on_success(title=obj['title'], status=pubstatus)
    
class NewCitationFormView(CitationFormMixin):

    form_class = NewCitationForm
    on_submit = 'create'
    
    def form_valid(self, form):
  
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))
        
        main_data = form.cleaned_data
        formset_data = self.create_from_formsets(form)
        if not isinstance(formset_data, dict):
            return formset_data
        
        main_data.update(formset_data)

        try:
            return self.replicate_data(data=main_data)
        except ValidationError as err:
            return self.render_to_response(self.get_context_data(form=form) | {
                'errors': '1 or more', 
                'extra_errors': {
                    'general':[getattr(err, 'message', str(err))]
                }
            })
        except Exception as err:
            raise err
    
    def get_initial(self):
        citation_data = {}
        if self.request.GET.get('title'):
            citation_data = CitationsSerializer(
                Citations.objects.filter(title=self.request.GET.get('title')).order_by('version').last()
            ).data

        for k, v in LABEL_MAPPINGS.items():
            citation_data[k] = citation_data.pop(v,None)

        initial = super().get_initial() | citation_data
        return initial
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['publishable'] = True
        return context

class EditCitationFormView(CitationFormMixin):

    form_class = EditCitationForm
    on_submit = 'update'

    # Needs to pre-populate form with existing values

    # Also adds context to either edit the existing record on form submission
    # Or creates a new record with the given data

    def form_valid(self, form):

        data = form.cleaned_data

        title = data.get('title')
        if data.get('version'): # Get the version onto the edit page data somehow.
            vn = data['version']
            instance = Citations.objects.get(title=title, version=vn)
        else:
            instance = Citations.objects.filter(title=self.kwargs['title']).order_by('version').last()

        # Handle edits to the joined attributes

        formset_data = self.create_from_formsets(form, title=title)
        if not isinstance(formset_data, dict):
            return formset_data
        data.update(formset_data)

        data['version'] = instance.version
        data['id'] = instance.id

        try:
            return self.replicate_data(instance=instance, data=data)
        except ValidationError as err:
            return self.render_to_response(self.get_context_data(form=form, title=title) | {
                'errors': '1 or more', 
                'extra_errors': {
                    'general':[getattr(err, 'message', str(err))]
                }
            })
        except Exception as err:
            raise err
        
    def get_initial(self):

        if self.request.GET.get('version'):
            vn = self.request.GET.get('version')
            citation_data = CitationsSerializer(
                Citations.objects.get(title=self.kwargs['title'], version=vn)
            ).data
        else:
            citation_data = CitationsSerializer(
                Citations.objects.filter(title=self.kwargs['title']).order_by('version').last()
            ).data

        for k, v in LABEL_MAPPINGS.items():
            citation_data[k] = citation_data.pop(v,None)

        initial = super().get_initial() | citation_data
        return initial
    
    def initial_formset_values(self, context):
        init = self.get_initial()
        initial_contacts = [init['primary']]
        initial_contacts += init.get("contacts", [])

        references = []
        for relation in self.serializer_class.Meta.citation_types:
            for v in init.get(relation):
                v['relation'] = reference_mapping.index(relation) + 1
                v['DOI'] = v['id']
                references.append(v)
        
        context["contact_formset"] = ContactFormSet(initial=initial_contacts)
        context['institution_formset'] = InstitutionFormSet(initial=init['institutions'])
        context['funder_formset']      = FunderFormSet(initial=init['funders'])
        context['reference_formset']   = ReferenceFormSet(initial=references)
        context['replica_formset']     = ReplicaFormSet()
        return context

    def new_version(self, title: str, **kwargs):
        version_requested = self.request.GET.get('version')
        latest = Citations.objects.filter(title=title).order_by('version').last().version

        if version_requested is None:
            version_requested = latest
        elif version_requested != latest:
            raise PermissionDenied(
                f'Unable to update version {version_requested} as there are later versions '
                f'already in existence (latest version: v{latest}'
            )
        return version_requested

    def get_context_data(self, title, **kwargs):
        context = super().get_context_data(title=title, **kwargs)

        # In order to be publishable, a record must have an empty DOI URL slot
        # - Already determined as editable if we're at this stage.
        # - Already determined as un-published as it's editable.
        publishable = True
        if Citations.objects.get(title=title, version=context['new_version']).doi_url != '':
            publishable = False
        if not bool(settings.DATACITE_API_URL):
            publishable = False
            
        context['publishable'] = publishable
            
        return context

class ConfirmDeleteCitationView(GenericRenderedView):
    template_name = 'delete_citation.html'
    model = Citations
    serializer_class = CitationsSerializer

    def dispatch(self, request, *args, **kwargs):
        title = kwargs.get('title') or request.GET.get('title')
        if title:
            institute = self.model.objects.filter(title=title).order_by('-version').last().institution_id
            if institute:
                if not request.user.user_permissions.filter(codename=f'edit_{institute}'):
                    return HttpResponseRedirect(reverse('citations:reviewer_request'))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, pk, **kwargs):
        context = super().get_context_data(**kwargs)
        context['citation'] = self.get_instance(pk=pk)

        return context
    
    def post(self, request, pk, *args, **kwargs):
        delete_instance(
            update_handler=handle_update,
            model=self.model,
            id=pk,
            user=request.user.username
        )
        return HttpResponseRedirect(reverse('citations:citations'))
    
class ReviewerRequestView(LoginRequiredMixin, GenericRenderedView, FormView):
    template_name='reviewer_request.html'
    form_class = InstitutionIdForm

    def get_institution_ids(self):
        return [c for c in Citations.objects.values_list('institution_id', flat=True).distinct() if c]
    
    def get_institutions(self):
        insts = {}
        for i in self.request.user.user_permissions.values_list('codename', flat=True):
            if 'edit' in i:
                insts[i.replace('edit_','')] = i
        return insts

    def get_user_permissions_text(self):
        perms = []
        for i in self.request.user.user_permissions.values_list('codename', flat=True):
            if 'edit' in i:
                perms.append(f'{i} (Edit citations belonging to Institution: {i.replace("edit_","")})')
        return perms

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user_permissions'] = self.get_user_permissions_text()
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['institution_ids'] = self.get_institution_ids()
        kwargs['preselect'] = self.get_institutions()

        return kwargs

    def form_valid(self, form):

        institutions = []
        for field in form.fields:
            if form.cleaned_data.get(field):
                institutions.append(field.replace('inst_',''))

        general = Permission.objects.get(codename='add_citations')
        change_permissions = not self.request.user.user_permissions.filter(pk=general.pk)

        for institution in institutions:
            perm_request = Permission.objects.get(codename=f'edit_{institution}')
            if not self.request.user.user_permissions.filter(pk=perm_request.pk):
                change_permissions = True
                
        if change_permissions:
            request_text = f':bell: Github user: {self.request.user.username} ({self.request.user.first_name} {self.request.user.last_name}) ' \
                f'is requesting Reviewer access (Create/Update/Delete) for the institutions: {", ".join(institutions)}'
            
            if settings.DEBUG:
                request_text += ' This is a test message'

            slack_client = WebClient(token=settings.SLACK_OAUTH_TOKEN)
            slack_client.chat_postMessage(
                channel=settings.SLACK_ESGF_CHANNEL,
                text=request_text,
                username='CEDA Citation SVC'
            )
            messages.success(self.request, f'Your request for permission to edit Citation records for {", ".join(institutions)} has been submitted.')
        else:
            messages.success(self.request, 'Your permissions have not been changed.')

        return HttpResponseRedirect(reverse('citations:citations'))