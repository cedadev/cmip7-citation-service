from rest_framework import serializers
from citations.models import (
    Institutions, 
    Parties, 
    FundingStreams,
    Citations,
    locate_institute,
    extract_from_orcid
)
from django.db import models

from citations.validators import validate_title
from citations.consumer.write import create_instance, update_instance, chain_new_objects

import hashlib
import json

def unwrap_request(data: dict, pk: str = None) -> dict:
    ndata = {}
    for k, v in data.items():

        if pk is not None and pk != k:
            continue

        if isinstance(v,list) and len(v) == 1:
            ndata[k] = v[0]
        elif isinstance(v,dict):
            ndata[k] = unwrap_request(v)
        else:
            ndata[k] = v

    return ndata

class GenericSerializerMixin(serializers.ModelSerializer):

    def create(self, validated_data):
        """
        Create and return an Institution instance given validated data.
        """
        validated_data = unwrap_request(validated_data)
        filter_data    = unwrap_request(validated_data, pk=self.Meta.model._meta.pk.name)
        if len(filter_data.keys()) != 0:
            # Entry supplied with primary key, check against existing models
            if self.Meta.model.objects.filter(**filter_data):
                return self.update(
                    self.Meta.model.objects.get(**filter_data),
                    validated_data
                )

        return create_instance(self.Meta.model, required_fields=self.Meta.required_fields, **validated_data)
    
    def update(self, instance, validated_data: dict):
        """
        Update and return an existing `Snippet` instance, given the validated data.
        """

        # "Quirky behaviour" allows creation of a new instance via this mechanism.
        # Need to experiment deleting the old instance.

        validated_data = unwrap_request(validated_data)
        instance = update_instance(self.Meta.model, required_fields=self.Meta.required_fields,**validated_data)
        return instance

class InstitutionsSerializer(GenericSerializerMixin):
    class Meta:
        model = Institutions
        required_fields = ['name']
        fields = ['name','acronym','country','id']
        relations=[]

    def to_internal_value(self, data):

        data = data.copy()

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

    def to_internal_value(self, data):

        data = data.copy()

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
            ).pk for a in affiliation_data]

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

    def to_internal_value(self, data):

        data = data.copy()
        if 'affiliation' in data:
            affiliation = data.pop('affiliation')

            data['affiliation_id'] = chain_new_objects(
                {'name': affiliation}, 
                InstitutionsSerializer, 
                Institutions, 
                filter_kwargs={'name':affiliation}
            ).pk

        data['id'] = hashlib.sha1(data['name'].encode()).hexdigest()

        return data

class CitationsSerializer(GenericSerializerMixin):
    primary      = PartiesSerializer(required=False)
    contacts     = PartiesSerializer(required=False, many=True)
    institutions = InstitutionsSerializer(required=False, many=True)
    funders      = FundingStreamsSerializer(required=False, many=True)

    class Meta:
        model = Citations
        fields = [
            'title', 'abstract', 'drs_url',
            'doi_url', 'rights', 'license',
            'primary', 'contacts', 'institutions',
            'funders','id', 'version',
            'mip_era','activity_id','institution_id',
            'source_id','experiment_id'
        ]
        required_fields=[
            'title','version'
        ]

        relations=['contacts','institutions','funders']

    def validate(self, data):
        data = super().validate(data)
        data = dict(data) | validate_title(data['title'])
        return data
    
    def update(self, instance, validated_data):

        if instance.published and instance.doi_url is None:
            validated_data['published'] = False

        if instance.doi_url is not None:
            validated_data['published'] = True

        return super().update(instance, validated_data)

    def to_internal_value(self, data: dict):
        """
        Update the data in a POST request.

        Locate or create references based on the provided information.
        """

        data = data.copy()

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
            primary = data.pop('primary')[0]

            # This does not correctly create institution objects
            search_primary = chain_new_objects(primary, PartiesSerializer, Parties, 
                                               filter_kwargs=PartiesSerializer.Meta.required_fields,
                                               optionals=optional_party)
            data['primary_id'] = search_primary.pk

        if data.get('contacts'):
            contacts = []
            for contact in data.pop('contacts')[0]:
                search_contact = chain_new_objects(contact, PartiesSerializer, Parties,
                                                    filter_kwargs=PartiesSerializer.Meta.required_fields,
                                                    optionals=optional_party)
                contacts.append(search_contact)
            data['contacts'] = [c.pk for c in contacts]

        # Unpack funders
        if data.get('funders'):
            funders = []
            for funder in data.pop('funders')[0]:
                search_funder = chain_new_objects(funder, FundingStreamsSerializer, FundingStreams,
                                                  filter_kwargs=FundingStreamsSerializer.Meta.required_fields,
                )#onward_chain=['affiliation'])
                funders.append(search_funder)
            data['funders'] = [f.pk for f in funders]

        # Unpack institutions
        if data.get('institutions'):
            institutions = []
            for institution in data.pop('institutions')[0]:
                search_institution = chain_new_objects(institution, InstitutionsSerializer, Institutions,
                                                       filter_kwargs=InstitutionsSerializer.Meta.required_fields,
                                                       )
                institutions.append(search_institution)
            data['institutions'] = [i.pk for i in institutions]

        # Unpack references

        #for reference in data.get('references'):

        #    print(reference)

        data['published'] = False
        if data.get('doi_url',None) is not None:
            data['published'] = True

        return data