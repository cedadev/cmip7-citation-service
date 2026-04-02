import hashlib
import json

from django.db import models
from rest_framework import serializers
from rest_framework.exceptions import MethodNotAllowed

from citations.consumer.write import (chain_new_objects, create_instance,
                                      update_instance)
from citations.models import (Citations, FundingStreams, Institutions, Parties,
                              extract_from_orcid, locate_institute)
from citations.validators import validate_title


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
            if k in self.Meta.fields or k.replace('_id','') in self.Meta.id_relations:
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

        filtered_data  = self.filter_data(validated_data)

        for k in self.Meta.required_fields:
            if k in getattr(self.Meta,'id_relations',[]):
                if k+'_id' not in filtered_data:
                    raise MethodNotAllowed(f'Submission without "{k}" field')
                continue

            if k not in filtered_data :
                raise MethodNotAllowed(f'Submission without "{k}" field')

        pk    = filtered_data[self.Meta.model._meta.pk.name]

        filtered_data = self.replace_id_relations(filtered_data)

        if self.Meta.model.objects.filter(pk=pk):
            return self.update(
                self.Meta.model.objects.get(pk=pk),
                filtered_data
            )

        create_instance(self.Meta.model, required_fields=self.Meta.required_fields, **filtered_data)
        return filtered_data
    
    def update(self, instance, validated_data: dict):
        """
        Update and return an existing `Snippet` instance, given the validated data.
        """

        # "Quirky behaviour" allows creation of a new instance via this mechanism.
        # Need to experiment deleting the old instance.

        filtered_data  = self.filter_data(validated_data)
        filtered_data  = self.replace_id_relations(filtered_data)
        filtered_data.pop('id')

        if len(filtered_data.keys()) == 0:
            raise MethodNotAllowed('No updates supplied')

        for field in getattr(self.Meta,'immutable_fields',[]):
            if filtered_data.get(field) != getattr(instance, field) and filtered_data.get(field,None):
                raise MethodNotAllowed(f'The field "{field}" is immutable')

        update_instance(self.Meta.model, id=instance.id, **filtered_data)
        return filtered_data

class InstitutionsSerializer(GenericSerializerMixin):
    class Meta:
        model = Institutions
        required_fields = ['name']
        fields = ['name','acronym','country','id']
        relations=[]

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
            'title','version', 'primary'
        ]
        non_replicating_fields=['experiment_id']
        id_relations = ['primary']

        relations=['contacts','institutions','funders']

    def create(self, validated_data):
        # Only run if the data title is new
        if 'title' in validated_data:
            facets = validate_title(validated_data['title'])
            for k in facets.keys():

                # Fill if not overridden by input.
                if validated_data.get(k,None) is None:
                    validated_data[k] = facets[k]
        return super().create(validated_data)
    
    def update(self, instance, validated_data):

        if instance.published and instance.doi_url is None:
            validated_data['published'] = False

        if instance.doi_url is not None:
            validated_data['published'] = True

        return super().update(instance, validated_data)

    def fill_data_parameters(self, data: dict):
        """
        Update the data in a POST request.

        Locate or create references based on the provided information.
        """

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

        #for reference in data.get('references'):

        #    print(reference)

        data['published'] = False
        if data.get('doi_url',None) is not None:
            data['published'] = True

        return data