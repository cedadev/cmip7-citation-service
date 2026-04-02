import copy
import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import CharField, ForeignKey, Q, TextField
from django.db.models.functions import Lower
from django.http import (HttpResponseForbidden,
                         HttpResponseNotFound, HttpResponseRedirect)
from django.urls import reverse
from django.views.generic.base import TemplateView
from django.views.generic.edit import FormView
from rest_framework import generics, mixins, permissions, status
from rest_framework.authentication import TokenAuthentication
from rest_framework.response import Response

from citations.consumer.write import chain_new_objects, delete_instance
from citations.forms import (ContactFormSet, EditCitationForm, FunderFormSet,
                             InstitutionFormSet, NewCitationForm,
                             ReplicaFormSet)
from citations.models import Citations, FundingStreams, Institutions, Parties
from citations.serializers import (CitationsSerializer,
                                   FundingStreamsSerializer,
                                   InstitutionsSerializer, PartiesSerializer)


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
    
    def create(self, request, *args, **kwargs):
        data=unwrap_request(request.data)
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
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
                mutable[field] = json.loads(mutable[field])[0]
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
    
def check_changes(instance, data):
    changed_data = {}
    for attr, value in data.items():
        if str(value) != str(getattr(instance, attr, None)):
            changed_data[attr] = value
    return changed_data

class CitationFormMixin(GenericRenderedView, FormView):

    template_name = "edit_citation.html"
    model = Citations
    serializer_class = CitationsSerializer

    label_mappings = {
        'activity':'activity_id',
        'experiment': 'experiment_id',
        'source': 'source_id',
        'institution': 'institution_id'
    }

    def redirect_on_success(self, title: str = None):
        if title is not None:
            messages.success(self.request, 'Your citation updates have been submitted and will appear here when they have been processed.')
            return HttpResponseRedirect(reverse('citations:citation', args=[title]))
        messages.success(self.request, 'Your citations have been submitted and will appear here when they have been processed.')
        return HttpResponseRedirect(reverse('citations:citations'))
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.request.POST:
            context['contact_formset'] = ContactFormSet(self.request.POST)
            context['institution_formset'] = InstitutionFormSet(self.request.POST)
            context['funder_formset'] = FunderFormSet(self.request.POST)
            context['replica_formset'] = ReplicaFormSet(self.request.POST)
        else:
            context['contact_formset'] = ContactFormSet()
            context['institution_formset'] = InstitutionFormSet()
            context['funder_formset'] = FunderFormSet()
            context['replica_formset'] = ReplicaFormSet()

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
            else:
                changed_data = formdata

            if changed_data:
                inst = chain_new_objects(
                    data=changed_data | filter_kwargs,
                    serializer=serializer,
                    model=model,
                    filter_kwargs=serializer.Meta.required_fields,
                    allow_update=allow_update,
                    fill_data_parameters=True) # Allowed updates from citation form directly to contacts
            pks.append(inst.pk)
        return pks

    def create_from_formsets(self, form, **kwargs) -> dict:

        contact_formset     = ContactFormSet(self.request.POST)
        institution_formset = InstitutionFormSet(self.request.POST)
        funder_formset      = FunderFormSet(self.request.POST)

        errors = 0

        error_map = {}
        for formset in [contact_formset, institution_formset, funder_formset]:
            for form_pt in formset:
                if not form_pt.is_valid():
                    error_map[formset.prefix] = form.errors
                    errors += 1

        if errors > 1:
            return self.render_to_response(self.get_context_data(form=form, **kwargs) | {'extra_errors':error_map, 'errors': errors})
        
        main_data = {}
        main_data['contacts'] = []
        main_data['institutions'] = []
        main_data['funders'] = []
        
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
                    'extra_errors': {
                        'contact':["A primary contact must be provided"],
                        'errors': 1
                }})

        main_data['institutions'] = self.clean_formset_data(
            institution_formset, InstitutionsSerializer, Institutions)

        main_data['funders'] = self.clean_formset_data(
            funder_formset, FundingStreamsSerializer, FundingStreams
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

        for v, k in self.label_mappings.items():
            data[k] = data.pop(v,None)

        serializer = self.serializer_class(
            instance=instance,
            data=data)
        
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()

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
                serializer.save()
            if len(replicas) > 0:
                return self.redirect_on_success()
            
        return self.redirect_on_success(title=obj['title'])

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

        return self.replicate_data(data=main_data)
    
    def get_initial(self):
        citation_data = {}
        if self.request.GET.get('title'):
            citation_data = CitationsSerializer(
                Citations.objects.filter(title=self.request.GET.get('title')).order_by('version').last()
            ).data

        for k, v in self.label_mappings.items():
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

        return self.replicate_data(instance=instance, data=data)
        

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

        for k, v in self.label_mappings.items():
            citation_data[k] = citation_data.pop(v,None)

        initial = super().get_initial() | citation_data
        return initial

    def get_context_data(self, title, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.request.method == "POST":
            context['contact_formset']     = ContactFormSet(self.request.POST)    
            context['institution_formset'] = InstitutionFormSet(self.request.POST)
            context['funder_formset']      = FunderFormSet(self.request.POST)
            context['replica_formset']     = ReplicaFormSet(self.request.POST)
        else:
            # Pull the initial list you created in get_initial()
            init = self.get_initial()
            initial_contacts = [init['primary']]
            initial_contacts += init.get("contacts", [])
            context["contact_formset"] = ContactFormSet(initial=initial_contacts)
            context['institution_formset'] = InstitutionFormSet(initial=init['institutions'])
            context['funder_formset']      = FunderFormSet(initial=init['funders'])
            context['replica_formset']     = ReplicaFormSet()

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