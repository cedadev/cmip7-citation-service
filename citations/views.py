from citations.models import (
    Institutions,
    Parties,
    FundingStreams,
    Citations
)
from citations.serializers import (
    InstitutionsSerializer,
    PartiesSerializer,
    FundingStreamsSerializer,
    CitationsSerializer
)

from citations.forms import(
    EditCitationForm,
    NewCitationForm,
    ContactFormSet
)

from citations.consumer.write import chain_new_objects, delete_instance

from rest_framework.authentication import TokenAuthentication
from rest_framework import status
from rest_framework.response import Response
from django.core import serializers
from django.core.paginator import Paginator
from django.urls import reverse
from django.http import HttpResponseRedirect, HttpResponseNotFound
from rest_framework import permissions

from rest_framework import mixins
from rest_framework import generics

from rest_framework.exceptions import APIException

from django.views.generic.base import TemplateView
from django.views.generic.edit import FormView
from django.views.generic import ListView
from django.contrib.sites import shortcuts
from django.http import HttpResponse, HttpResponseForbidden
from django.contrib.auth.mixins import LoginRequiredMixin
from django.conf import settings
from django.db.models import Q, CharField, TextField, ForeignKey
from django.db.models.functions import Lower
from django.core.exceptions import PermissionDenied

import json

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
    
class IntroView(LoginRequiredMixin,GenericRenderedView):
    login_url = settings.LOGIN_URL
    template_name = 'intro.html'

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
    order_by = '-version'

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

        context['editable'] = citation.editable
        if citation.version != latest_version:
            context['latest_version'] = latest_version

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
    
    def initialize_request(self, request, *args, **kwargs):
        """
        Decode Information Given to POST requests
        """
        req = super().initialize_request(request, *args, **kwargs)

        # Modify req.data here
        mutable = req.data.copy()
        for field in self.json_fields:
            if mutable.get(field,'') != '' and isinstance(mutable.get(field),str):
                mutable[field] = json.loads(mutable[field])
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
            model=self.model,
            id=instance.id)
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    def initialize_request(self, request, *args, **kwargs):
        """
        Decode Information Given to POST requests
        """
        req = super().initialize_request(request, *args, **kwargs)

        # Modify req.data here
        mutable = req.data.copy()
        for field in self.json_fields:
            if mutable.get(field,'') != '' and isinstance(mutable.get(field),str):
                mutable[field] = json.loads(mutable[field])
        req._full_data = mutable  # override parsed data

        return req

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
    json_fields = ['primary','funders','institutions','contacts']

class SpecificCitationAPIView(SpecificAPIView):
    """
    List all funding streams.
    """
    model = Citations
    queryset = Citations.objects.all()
    serializer_class = CitationsSerializer

    json_fields = ['primary','funders','institutions','contacts']

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if not instance.editable:
            return HttpResponseForbidden(
                f'Editing the record {instance.id} is forbidden'
            )

        return super().update(request, *args, **kwargs)
    
class CitationFormMixin(GenericRenderedView, FormView):

    template_name = "edit_citation.html"
    model = Citations
    serializer_class = CitationsSerializer

    def redirect_on_success(self, title):
        return HttpResponseRedirect(reverse('citations:citation', args=[title]))
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.request.POST:
            context['contact_formset'] = ContactFormSet(self.request.POST)
        else:
            context['contact_formset'] = ContactFormSet()

        context['on_submit'] = self.on_submit
        
        if self.request.GET.get('title'):
            # Create from Previous
            context['new_version'] = Citations.objects.filter(title=self.request.GET.get('title')).order_by('version').last().version + 1
        elif self.kwargs.get('title'):
            # Edit Current
            context['new_version'] = Citations.objects.filter(title=self.kwargs.get('title')).order_by('version').last().version
        else:
            # Create New
            context['new_version'] = 1

        required_fields = []
        for serializer in [
            InstitutionsSerializer,
            PartiesSerializer,
            FundingStreamsSerializer,
            CitationsSerializer
        ]:
            required_fields += [
                f[0].upper() + f[1:].replace('_',' ') for f in serializer.Meta.required_fields
            ]

        context['required_fields'] = list(set(required_fields))
        context['publishable'] = False
        return context

class NewCitationFormView(CitationFormMixin):

    form_class = NewCitationForm
    on_submit = 'create'
    
    def form_valid(self, form):

        contact_formset = ContactFormSet(self.request.POST)
        if not contact_formset.is_valid():
            return self.form_invalid(form)
        
        main_data = form.cleaned_data
        main_data['contacts'] = []
        
        primary_index = int(self.request.POST.get("primary_contact"))
        for i, contact_form in enumerate(contact_formset):
            inst = chain_new_objects(
                data=contact_form.cleaned_data,
                serializer=PartiesSerializer,
                model=Parties,
                filter_kwargs=PartiesSerializer.Meta.required_fields)
            
            if i == primary_index:
                main_data['primary_id'] = inst.pk
            else:
                main_data['contacts'].append(inst.pk)

        serializer = self.serializer_class(data=main_data)
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return self.redirect_on_success(title=obj.title)
    
    def get_initial(self):
        citation_data = {}
        if self.request.GET.get('title'):
            citation_data = CitationsSerializer(
                Citations.objects.filter(title=self.request.GET.get('title')).order_by('version').last()
            ).data

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

        title = self.request.GET.get('title')
        if self.request.GET.get('version'):
            vn = self.request.GET.get('version')
            instance = Citations.objects.get(title=title, version=vn)
        else:
            instance = Citations.objects.filter(title=self.kwargs['title']).order_by('version').last()

        data = form.cleaned_data
        data['version'] = instance.version
        data['id'] = instance.id

        serializer = self.serializer_class(
            instance=instance,
            data=data)
        
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return self.redirect_on_success(title=obj.title)

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

        initial = super().get_initial() | citation_data
        return initial

    def get_context_data(self, title, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.request.method == "POST":
            context["contact_formset"] = ContactFormSet(self.request.POST)
        else:
            # Pull the initial list you created in get_initial()
            init = self.get_initial()
            initial_contacts = [init['primary']]
            initial_contacts += init.get("contacts", [])
            context["contact_formset"] = ContactFormSet(initial=initial_contacts)

        version_requested = self.request.GET.get('version')
        latest = Citations.objects.filter(title=title).order_by('version').last().version

        if version_requested is None:
            version_requested = latest
        elif version_requested != latest:
            raise PermissionDenied(
                f'Unable to update version {version_requested} as there are later versions '
                f'already in existence (latest version: v{latest}'
            )

        context['new_version'] = version_requested

        # In order to be publishable, a record must have an empty DOI URL slot
        # - Already determined as editable if we're at this stage.
        # - Already determined as un-published as it's editable.
        if Citations.objects.get(title=title, version=context['new_version']).doi_url == '':
            context['publishable'] = True
            
        return context
    
class ConfirmDeleteCitationView(GenericRenderedView):
    template_name = 'delete_citation.html'
    model = Citations
    serializer_class = CitationsSerializer

    def get_context_data(self, pk, **kwargs):
        context = super().get_context_data(**kwargs)
        context['citation'] = self.get_instance(pk=pk)

        return context
    
    def post(self, request, pk, *args, **kwargs):
        delete_instance(
            model=self.model,
            id=pk
        )
        return HttpResponseRedirect(reverse('citations:citations'))