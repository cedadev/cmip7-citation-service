from rest_framework import serializers
from citations.models import (
    Institutions, 
    Parties, 
    FundingStreams,
    Citations,
    locate_institute
)

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


        return self.Meta.model.objects.create(**validated_data)
    
    def update(self, instance, validated_data: dict):
        """
        Update and return an existing `Snippet` instance, given the validated data.
        """

        # "Quirky behaviour" allows creation of a new instance via this mechanism.
        # Need to experiment deleting the old instance.

        validated_data = unwrap_request(validated_data)
        for k, v in validated_data.items():
            if hasattr(instance, k):
                setattr(instance, k, v)

        instance.save()
        return instance

class InstitutionSerializer(GenericSerializerMixin):
    class Meta:
        model = Institutions
        required_fields = ['name']
        fields = ['name','acronym','country','id']

class PartySerializer(GenericSerializerMixin):
    affiliations = InstitutionSerializer(required=False, many=True)
    class Meta:
        model = Parties
        required_fields = ['first_name', 'last_name']
        immutable_fields = ['first_name', 'last_name', 'middle_names']
        fields = immutable_fields + ['email','orcid','affiliations','id']

    def create(self, validated_data):
        """
        Create and return an Institution instance given validated data.
        """
        validated_data = unwrap_request(validated_data)
        affiliations = validated_data.pop('affiliations',[])
        instance = self.Meta.model.objects.create(**validated_data)
        for aff in affiliations:
            instance.affiliations.add(aff)
        return instance

    def to_internal_value(self, data):

        data = data.copy()
        if data.get('affiliations',None) is not None:
            # Properly connect non-blank affiliations
            affils = []
            for affiliation in data['affiliations']:
                inst_exists = Institutions.objects.filter(name=affiliation)
                inst_meta = locate_institute(affiliation)
                if inst_meta is None and inst_exists is None:
                    raise ValueError(
                        f"Unable to locate data for affiliation {affiliation}"
                    )
                
                if not inst_exists:
                    institute = Institutions.objects.create(**inst_meta)
                    institute.save()
                else:
                    try:
                        institute = Institutions.objects.get(name=affiliation)
                    except Institutions.MultipleObjectsReturned:
                        raise ValueError(
                            f"Multiple institutions with the name {affiliation}."
                        )
                affils.append(institute)
            data['affiliations'] = affils

        # Add ID from hashed version of first and last names?
        naming_hash = data['first_name'] + data.get('middle_names','') + data.get('last_name')
        party_id = hashlib.sha1(naming_hash.encode()).hexdigest()

        data['id'] = party_id

        return data

class FundingStreamSerializer(GenericSerializerMixin):
    affiliation = serializers.StringRelatedField(required=False)
    
    class Meta:
        model = FundingStreams
        required_fields = ['name']
        fields = ['name','affiliation']

    def to_internal_value(self, data):
        if 'affiliation' in data:
            affiliation = data['affiliation']

            inst_exists = Institutions.objects.filter(name=affiliation)
            inst_meta = locate_institute(affiliation)
            if inst_meta is None and inst_exists is None:
                raise ValueError(
                    f"Unable to locate data for affiliation {affiliation}"
                )
            
            if not inst_exists:
                institute = Institutions.objects.create(**inst_meta)
                institute.save()
            else:
                try:
                    institute = Institutions.objects.get(name=affiliation)
                except Institutions.MultipleObjectsReturned:
                    raise ValueError(
                        f"Multiple institutions with the name {affiliation}."
                    )
            data = data.copy()
            data['affiliation'] = institute

        return data

class CitationSerializer(GenericSerializerMixin):
    primary      = PartySerializer(required=False)
    contacts     = PartySerializer(required=False, many=True)
    institutions = InstitutionSerializer(required=False, many=True)
    funders      = FundingStreamSerializer(required=False, many=True)

    class Meta:
        model = Citations
        fields = [
            'title', 'abstract', 'drs_url',
            'doi_url', 'rights', 'license',
            'primary', 'contacts', 'institutions',
            'funders','id'
        ]

    def create(self, validated_data):
        """
        Create and return an Institution instance given validated data.
        """
        validated_data = unwrap_request(validated_data)
        funders      = validated_data.pop('funders',[])
        institutions = validated_data.pop('institutions',[])

        instance = self.Meta.model.objects.create(**validated_data)
        for funder in funders:
            instance.funders.add(funder)
        for inst in institutions:
            instance.institutions.add(inst)
        instance.save()
        return instance

    def to_internal_value(self, data):
        """
        Update the data in a POST request.

        Locate or create references based on the provided information.
        """

        if data.get('version') is not None or data.get('identifier') is not None:
            raise ValueError(
                'Unsupported for updates via this mechanism'
            )

        data = data.copy()

        # Version is auto-assigned
        version = len(self.Meta.model.objects.filter(title=data['title'])) + 1
        data['version'] = version

        # Identifier is auto-assigned
        id = data['title'] + '_v' + str(data['version'])
        data['id'] = id

        optional_party = list(set(PartySerializer.Meta.immutable_fields) - set(PartySerializer.Meta.required_fields))
        # Unpack primaries, contacts
        if data.get('primary'):
            primary = json.loads(data['primary'])
            search_primary = chain_new_objects(primary, PartySerializer, Parties, 
                                               filter_kwargs=PartySerializer.Meta.required_fields,
                                               optionals=optional_party)
            data['primary'] = search_primary

        if data.get('contacts'):
            contacts = []
            for contact in json.loads(data['contacts']):
                search_contact = chain_new_objects(contact, PartySerializer, Parties,
                                                    filter_kwargs=PartySerializer.Meta.required_fields,
                                                    optionals=optional_party)
                contacts.append(search_contact)
            data['contacts'] = contacts

        # Unpack funders
        if data.get('funders'):
            funders = []
            for funder in json.loads(data['funders']):
                search_funder = chain_new_objects(funder, FundingStreamSerializer, FundingStreams,
                                                  filter_kwargs=FundingStreamSerializer.Meta.required_fields,
                )#onward_chain=['affiliation'])
                funders.append(search_funder)
            data['funders'] = funders

        # Unpack institutions
        if data.get('institutions'):
            institutions = []
            for institution in json.loads(data['institutions']):
                search_institution = chain_new_objects(institution, InstitutionSerializer, Institutions,
                                                       filter_kwargs=InstitutionSerializer.Meta.required_fields,
                                                       )
                institutions.append(search_institution)
            data['institutions'] = institutions

        # Unpack references

        #for reference in data.get('references'):

        #    print(reference)

        return data

def chain_new_objects(
        data: dict, 
        serializer: GenericSerializerMixin, 
        model, 
        filter_kwargs: list, 
        optionals: list = None
    ):
    optionals = optionals or []
    filters = {k: data[k] for k in filter_kwargs}
    for opt in optionals:
        if data.get(opt):
            filters[opt] = data[opt]
    search = model.objects.filter(**filters)

    # Create instance if not specified.
    if not search:
        serial = serializer(data=data)
        serial.is_valid(raise_exception=True)
        instance = model.objects.create(**serial.validated_data)
        instance.save()
    # Should return newly created instance or existing one
    instance = model.objects.get(**filters)
    return instance