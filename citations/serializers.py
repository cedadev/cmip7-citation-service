import hashlib
import json
import re

import requests
from django.conf import settings
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db import models
from rest_framework import serializers
from rest_framework.exceptions import MethodNotAllowed, ParseError
from django.core.exceptions import ValidationError

from datetime import datetime

from citations.consumer.write import create_instance, update_instance
from citations.external import publish_record
from citations.models import (Citations, FundingStreams, Institutions, Parties,
                              References, extract_from_orcid, locate_institute)
from citations.validators import validate_title, validate_cmip7_facets, validate_cordex_facets
from citations.utils import LABEL_MAPPINGS, ESGVOC_FACET_LABELS

try:
    import esgvoc.api as ev
except ImportError:
    ev = None

def mint_doi_for_data(data: dict):
    """
    'Data' is the partially serialized content for the record to be published.

    - Expand all creators (proper serialization)
    - Expand all funders
    - Expand all references
    - Send data to publish record
    
    """

    creators = [PartiesSerializer(instance=Parties.objects.get(pk=data['primary_id'])).data] + \
        [PartiesSerializer(instance=Parties.objects.get(pk=pk)).data for pk in data['contacts']]
        
    
    data['creators'] = creators

    funders = [
        FundingStreamsSerializer(
            instance=FundingStreams.objects.get(pk=pk)).data for pk in data['funders']
    ]

    data['funders'] = funders

    for reltype in ['cites','is_cited_by','is_referenced_by']:
        data[reltype] = [
            ReferencesSerializer(
                instance=References.objects.get(pk=pk)).data for pk in data.get(reltype,[])
        ]
    
    status, pubdata = publish_record(data)
    if status:
        return pubdata

def institution_mappings(institution_id: str) -> str:

    try:
        mappings = requests.get(settings.INSTITUTION_MAPPINGS_URL).json()
        return mappings[institution_id.lower()]
    except Exception:
        if not ev:
            return {'name': institution_id, 'acronym': institution_id}
        
    # Get the institution from esgvoc
    component = ev.get_term_in_collection(
        project_id='cmip7',
        collection_id='institution',
        term_id=institution_id) or ev.get_term_in_collection(
        project_id='cmip7',
        collection_id='institution',
        term_id=institution_id.lower())
    
    data = {'name': institution_id, 'acronym': institution_id}
    if component:
        country = None
        try:
            country = component.members[0].location[0].country
        except Exception as e:
            pass

        data.update({
            'name': getattr(component,'description',institution_id), 
            'acronym': getattr(component,'acronyms',[institution_id])[0],
        })
        if country: 
            data.update({'country': country})
    return data
    
     
def title_from_facets(data: dict, validate_all: bool = False, raise_exceptions: bool = True):

    if bool(data.get('domain_id')):
        # CORDEX Data
        if validate_all:
            validate_cordex_facets(data, raise_exceptions=raise_exceptions)

        return f'{data["mip_era"]}.{data["activity_id"]}.{data["domain_id"]}.{data["institution_id"]}.{data["experiment_id"]}.{data["source_id"]}'
    
    if validate_all:
        validate_cmip7_facets(data, raise_exceptions=raise_exceptions)
    
    return f'{data["mip_era"]}.{data["activity_id"]}.{data["institution_id"]}.{data["source_id"]}.{data["experiment_id"]}'

def obtain_all_references(data: dict) -> dict:
    """
    Obtain Citation references from the EMD (ESGVOC)
    
    Prevent adding a reference if it already exists.
    """

    if not ev:
        return {}
    
    cites = []
    for fl in ESGVOC_FACET_LABELS:
        component = ev.get_term_in_collection(project_id='cmip7',collection_id=fl,term_id=data[LABEL_MAPPINGS.get(fl,fl)].lower())

        if not component:
            continue
        if not hasattr(component,'references'):
            continue

        for ref in component.references:

            if ref.doi in ref.citation:
                citeas = ref.citation
            else:
                citeas = f'{ref.citation} {ref.doi}'

            title = getattr(ref,'title',None) or re.search(r'^.*?\d{4}', ref.citation).group(0)
            cites.append({
                'title':title,
                'citeas':citeas,
                'id':ref.doi
            })

    return cites

def assemble_license_info(data: dict) -> str:
    """
    Determine the paragraph of text to use for the license.
    """
    license = []
    if hasattr(settings, 'GENERAL_INFO'):
        license += settings.GENERAL_INFO.split('.')
    if hasattr(settings, 'CITATION_GUIDANCE'):
        license += settings.CITATION_GUIDANCE.split('.')

    license.append(f'Published under {data["rights"]}')

    return '. '.join(license)
    
def abstract_from_esgvoc(data: dict):
    """
    Determine the paragraph of abstract text from esgvoc parameters.
    """

    if not ev:
        return ''
    
    facet_descs = {
        'activity': '',
        'source': '',
        'institution': ['Produced by: ', ' (Using Model/Source: ', ' with Experiment ',')'],
        'mip_era': 'MIP Era: ',
        'experiment': '',
        'domain': 'CORDEX Domain: '
    }

    abstract = []
    for fl in ESGVOC_FACET_LABELS:
        entry = []
        if not bool(data.get(LABEL_MAPPINGS.get(fl,fl))):
            continue

        component = ev.get_term_in_collection(project_id='cmip7',collection_id=fl,term_id=data[LABEL_MAPPINGS.get(fl,fl)].lower())

        entry.append(getattr(component,"description",data[LABEL_MAPPINGS.get(fl,fl)]))

        if getattr(component,"labels",None):
            entry.append(','.join(component.labels))

        if not entry:
            continue

        if isinstance(facet_descs[fl],list):
            # Rendering institution description
            descs = facet_descs[fl]
            abstract.append(
                descs[0] + ' - '.join(entry) + descs[1] + data['source_id'] + descs[2] + data['experiment_id'] + descs[3]
            )
        else:
            abstract.append(facet_descs[fl] + ' - '.join(entry))

    if abstract and hasattr(settings, 'GENERAL_INFO'):
        abstract += [settings.GENERAL_INFO]

    if abstract and hasattr(settings, 'CEDA_INFO'):
        abstract += [settings.CEDA_INFO]

    return '\n\n'.join([a.replace('\n','') for a in abstract])

def chain_new_objects(
        data: dict, 
        serializer: serializers.ModelSerializer, 
        model: type[models.Model], 
        filter_kwargs: list, 
        optionals: list = None,
        allow_update: bool = False,
    ) -> str:
    """
    Validate new model instances.
    """

    optionals = optionals or []
    filters = {k: data.get(k) for k in filter_kwargs if k in data}
    for opt in optionals:
        if data.get(opt):
            filters[opt] = data[opt]
    instance = model.objects.filter(**filters)

    # Create instance if not specified.
    if not instance:
        serial = serializer(data=data)
        serial.is_valid(raise_exception=True)
        serial.save()
        inst_pk = serial.instance['id']
    else:
        instance = instance[0]
        serial = serializer(data=data, instance=instance)

        serial.is_valid(raise_exception=True)
        update = False
        if allow_update:
            for k,v in data.items():
                if v != getattr(instance, k):
                    update = True

        if update:
            serial.save()
        inst_pk = serial.validated_data.get('id',instance.pk)

    # Should return newly created instance or existing one
    return inst_pk

class GenericSerializerMixin(serializers.ModelSerializer):

    def to_internal_value(self, data):

        data = data.copy()
        if self.context.get('view'):
            if 'pk' in self.context['view'].kwargs:
                data['id'] = self.context['view'].kwargs['pk']

        return data

    def filter_data(self, validated_data: dict) -> dict:
        filtered_data = {}
        validated_data = self.fill_data_parameters(validated_data)
        for k in list(validated_data.keys()):
            if k in self.Meta.fields or k.replace('_id','') in self.Meta.id_relations or k in self.Meta.internal_fields:
                filtered_data[k] = validated_data.get(k,None)
        
        return filtered_data
    
    def replace_id_relations(self, validated_data: dict) -> dict:

        for k in getattr(self.Meta, 'id_relations',[]):
            if k in validated_data:
                validated_data[k+'_id'] = validated_data.pop(k)
        return validated_data

    def create(self, validated_data):
        """
        Create and return an Institution instance given validated data.
        """

        publish: bool = validated_data.pop('publish',False)
        user_id: str  = validated_data.pop('user_id','anon')

        filtered_data  = self.filter_data(validated_data)

        for k in self.Meta.required_fields:
            if k in getattr(self.Meta,'id_relations',[]):
                if k+'_id' not in filtered_data:
                    raise MethodNotAllowed(f'Submission without "{k}" field')
                continue

            if k not in filtered_data and getattr(self.Meta,'field_mappings',dict()).get(k) not in filtered_data:
                raise MethodNotAllowed(f'Submission without "{k}" field')

        pk    = filtered_data[self.Meta.model._meta.pk.name]

        filtered_data = self.replace_id_relations(filtered_data)

        if self.Meta.model.objects.filter(pk=pk):
            return self.update(
                self.Meta.model.objects.get(pk=pk),
                filtered_data,
                publish=publish
            )
        
        if publish:
            pubdata = mint_doi_for_data(validated_data)
            if pubdata:
                filtered_data.update(pubdata)
        
        create_instance(self.Meta.model, user=user_id, update_handler=handle_update, required_fields=self.Meta.required_fields, **filtered_data)
        return filtered_data
    
    def update(self, instance, validated_data: dict):
        """
        Update and return an existing `Snippet` instance, given the validated data.
        """

        publish: bool = validated_data.pop('publish',False)
        user_id: str  = validated_data.pop('user_id','anon')

        # "Quirky behaviour" allows creation of a new instance via this mechanism.
        # Need to experiment deleting the old instance.

        filtered_data  = self.filter_data(validated_data)
        filtered_data  = self.replace_id_relations(filtered_data)
        filtered_data.pop('id',None)

        if len(filtered_data.keys()) == 0:
            raise MethodNotAllowed('No updates supplied')

        for field in getattr(self.Meta,'immutable_fields',[]):
            if filtered_data.get(field) != getattr(instance, field) and filtered_data.get(field,None):
                raise MethodNotAllowed(f'The field "{field}" is immutable')
            
        if publish:
            pubdata = mint_doi_for_data(validated_data)
            if pubdata:
                filtered_data.update(pubdata)

        update_instance(self.Meta.model, user=user_id, update_handler=handle_update, id=instance.id, **filtered_data)
        return filtered_data

class InstitutionsSerializer(GenericSerializerMixin):
    class Meta:
        model = Institutions
        required_fields = ['name']
        fields = ['name','acronym','country','id']
        relations=[]
        internal_fields=[]

    def fill_data_parameters(self, data):

        if not data.get('acronym',None) and not data.get('country',None):
            data.update(locate_institute(data['name']))

        data['id'] = hashlib.sha1(data['name'].encode()).hexdigest()
        return data

class PartiesSerializer(GenericSerializerMixin):
    affiliations = InstitutionsSerializer(required=False, many=True)
    class Meta:
        model = Parties
        required_fields = ['first_name', 'last_name']
        immutable_fields = ['first_name', 'last_name', 'middle_names']
        fields = immutable_fields + ['email','orcid','affiliations','id']
        relations = ['affiliations']
        internal_fields=[]

    def fill_data_parameters(self, data):

        affiliation_data = []
        if data.get('orcid',None):
            affiliation_data += extract_from_orcid(data['orcid'])

        if data.get('affiliations',None) is not None:
            # Properly connect non-blank affiliations
            affiliation_data += json.loads(data.pop('affiliations')[0])

        if not isinstance(affiliation_data, list):
            affiliation_data = [affiliation_data]

        if len(affiliation_data) > 0:
            data['affiliations'] = [chain_new_objects(
                {'name':a},
                InstitutionsSerializer,
                Institutions,
                filter_kwargs={'name':a},
            ) for a in affiliation_data]

        if 'id' not in data:
            # Add ID from hashed version of first and last names?
            naming_hash = data['first_name'] + data.get('middle_names','') + data.get('last_name')
            party_id = hashlib.sha1(naming_hash.encode()).hexdigest()

            data['id'] = party_id
        return data

class FundingStreamsSerializer(GenericSerializerMixin):
    affiliation = serializers.StringRelatedField(required=False)
    
    class Meta:
        model = FundingStreams
        required_fields = ['name']
        fields = ['name','affiliation','id']
        relations=[]
        id_relations = ['affiliation']
        internal_fields=[]

    def fill_data_parameters(self, data):

        if 'affiliation' in data:
            affiliation = data.pop('affiliation')

            data['affiliation_id'] = chain_new_objects(
                {'name': affiliation}, 
                InstitutionsSerializer, 
                Institutions, 
                filter_kwargs={'name':affiliation}
            )

        if 'id' not in data:
            data['id'] = hashlib.sha1(data['name'].encode()).hexdigest()

        return data

class ReferencesSerializer(GenericSerializerMixin):

    class Meta:
        model = References
        fields = ['title','citeas','id']
        required_fields = ['id']
        relations = []
        id_relations = []
        field_mappings = {
            'DOI':'id'
        }
        internal_fields=[]

    def fill_data_parameters(self, data):
        return data

class CitationsSerializer(GenericSerializerMixin):
    primary      = PartiesSerializer(required=False)
    contacts     = PartiesSerializer(required=False, many=True)
    institutions = InstitutionsSerializer(required=False, many=True)
    funders      = FundingStreamsSerializer(required=False, many=True)
    is_cited_by        = ReferencesSerializer(required=False, many=True)
    is_referenced_by   = ReferencesSerializer(required=False, many=True)
    cites              = ReferencesSerializer(required=False, many=True)

    class Meta:
        model = Citations
        citation_types = ['is_cited_by', 'is_referenced_by','cites']
        fields = [
            'title', 'abstract', 'drs_url',
            'doi_url', 'rights', 'license',
            'primary', 'contacts', 'institutions',
            'funders','id', 'version', 'publication_year',
            'mip_era','activity_id','domain_id','institution_id',
            'source_id','experiment_id', 'cites', 'is_cited_by', 'is_referenced_by'
        ]
        required_fields=[
            'title','version', 'primary'
        ]
        non_replicating_fields=['experiment_id','doi_url', 'publication_year']
        id_relations = ['primary']

        relations = [
            'contacts','institutions','funders',
            'is_cited_by','is_referenced_by','cites'
        ]
        internal_fields=['editable', 'published']

    def create(self, validated_data):

        # Only run if the data title is new

        # No longer pulling facets from title - these are provided and validated or they are not provided at all.
        # if 'title' in validated_data:
        #     facets = validate_title(validated_data['title'], raise_exceptions=True)
        #     for k in facets.keys():

        #         data_facet = validated_data.get(k,None)
        #         if data_facet is not None and data_facet != facets[k]:
        #             raise ParseError(f'Facet "{k}" does not match title facet: {facets[k]}')

        #         # Fill if not overridden by input.
        #         if data_facet is None:
        #             validated_data[k] = facets[k]
        # else:

        # If no title, must have all facets to construct title.

        # Enforces valid facets for all records - but don't have to match title structure.
        title = title_from_facets(validated_data, validate_all=True, raise_exceptions=True)
        if not bool(validated_data.get('title',False)):
            validated_data['title'] = title

        return super().create(validated_data)
    
    def update(self, instance, validated_data):

        if instance.published and not instance.doi_url:
            validated_data['published'] = False

        if validated_data.get('doi_url'):
            if instance.doi_url is not None or True:
                validated_data['editable'] = False
            validated_data['published'] = True

        return super().update(instance, validated_data)

    def fill_data_parameters(self, data: dict):
        """
        Update the data in a POST request.

        Locate or create references based on the provided information.
        """

        # Only add references if they are not already present
        for gr in obtain_all_references(data):
            new_ref = True
            for reftype in self.Meta.citation_types:
                if gr['id'] in data[reftype]:
                    new_ref = False
            if new_ref:
                data['cites'].append(gr)

        # Auto-fills
        if not bool(data.get('abstract')):
            data['abstract'] = abstract_from_esgvoc(data)
        if not bool(data.get('rights')):
            data['rights'] = settings.DEFAULT_RIGHTS # 'CC-BY-4.0' SPDX identifier
        if not bool(data.get('license')):
            data['license'] = assemble_license_info(data)
        
        if data.get('institution_id'):
            # Create new institution as below, and add to the main affiliated institutions

            inst_data = institution_mappings(data['institution_id'])

            institution = chain_new_objects(
                inst_data,
                InstitutionsSerializer,
                Institutions,
                filter_kwargs={'name': inst_data['name']},
                allow_update=True
            )
            if 'institutions' not in data:
                data['institutions'] = []

            data['institutions'].append(institution)

        if data.get('version') is None and data.get('id') is None:
            
            # Version is auto-assigned
            version = len(self.Meta.model.objects.filter(title=data['title'])) + 1
            data['version'] = version

            # Identifier is auto-assigned
            id = data['title'] + '_v' + str(data['version'])
            data['id'] = id

        optional_party = list(set(PartiesSerializer.Meta.immutable_fields) - set(PartiesSerializer.Meta.required_fields))
        # Unpack primaries, contacts
        if data.get('primary'):
            primary = data.pop('primary')
            if isinstance(primary,dict):
                # This does not correctly create institution objects
                search_primary = chain_new_objects(primary, PartiesSerializer, Parties, 
                                                filter_kwargs=PartiesSerializer.Meta.required_fields,
                                                optionals=optional_party)
                primary = search_primary
            data['primary_id'] = primary

        if data.get('contacts'):
            contacts = []
            for contact in data.pop('contacts'):
                if isinstance(contact,dict):
                    search_contact = chain_new_objects(contact, PartiesSerializer, Parties,
                                                        filter_kwargs=PartiesSerializer.Meta.required_fields,
                                                        optionals=optional_party)
                    contacts.append(search_contact)
                else:
                    contacts.append(contact)
            data['contacts'] = contacts

        # Unpack funders
        if data.get('funders'):
            funders = []
            for funder in data.pop('funders'):
                if isinstance(funder, dict):
                    search_funder = chain_new_objects(funder, FundingStreamsSerializer, FundingStreams,
                                                    filter_kwargs=FundingStreamsSerializer.Meta.required_fields,
                    )
                    funders.append(search_funder)
                else:
                    funders.append(funder)
            data['funders'] = funders

        # Unpack institutions
        if data.get('institutions'):
            institutions = []
            for institution in data.pop('institutions'):
                if isinstance(institution, dict):
                    search_institution = chain_new_objects(institution, InstitutionsSerializer, Institutions,
                                                        filter_kwargs=InstitutionsSerializer.Meta.required_fields,
                                                        )
                    institutions.append(search_institution)
                else:
                    institutions.append(institution)
            data['institutions'] = institutions

        # Unpack references
        for citation_type in self.Meta.citation_types:
            if not data.get(citation_type):
                continue
            references = []
            for ref in data.pop(citation_type):
                if isinstance(ref, dict):
                    reference = chain_new_objects(ref, ReferencesSerializer, References, 
                                                  filter_kwargs=ReferencesSerializer.Meta.required_fields,
                                                  allow_update=True)
                    references.append(reference)
                else:
                    references.append(ref)
            data[citation_type] = references

        data['published'] = False
        if data.get('doi_url',None):
            data['published'] = True

        return data

dj_tables = {
    'citations':Citations,
    'institutions': Institutions,
    'fundingstreams': FundingStreams,
    'parties': Parties,
    'references': References,
}

dj_serializers = {
    'citations': CitationsSerializer,
    'institutions': InstitutionsSerializer,
    'fundingstreams': FundingStreamsSerializer,
    'parties': PartiesSerializer,
    'references': ReferencesSerializer
}
    
def handle_update(table: str, method: str, content: dict):
    """
    Handle ANY ORM Request updates here."""

    model      = dj_tables[table.lower()]
    serializer = dj_serializers[table.lower()]
    pk = model._meta.pk.name

    match method:
        case "create":
            instance = model.objects.create(
                **{c:v for c,v in content.items() if c not in serializer.Meta.relations}
            )
            for r in serializer.Meta.relations:
                if r in content:
                    getattr(instance, r).set(content[r])
            instance.save()

        case "update":
            # Must have already validated that the primary key exists and does not change - frontend
            instance = model.objects.get(**{pk: content[pk]})
            content.pop(pk)
            for attr, value in content.items():
                if attr in serializer.Meta.relations:
                    attr_i = getattr(instance, attr)
                    attr_i.set(value)
                else:
                    setattr(instance, attr, value)
            instance.save()

        case "delete":
            model.objects.get(**{pk: content[pk]}).delete()