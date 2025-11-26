from rest_framework import serializers
from citations.models import (
    Institutions, 
    Authors, 
    FundingStreams,
    Citations
)

class GenericSerializerMixin(serializers.ModelSerializer):

    def create(self, validated_data):
        """
        Create and return an Institution instance given validated data.
        """

        return self.Meta.model.objects.create(**validated_data)
    
    def update(self, instance, validated_data: dict):
        """
        Update and return an existing `Snippet` instance, given the validated data.
        """
        for k, v in validated_data.items():
            if hasattr(instance, k):
                setattr(instance, k, v)

        instance.save()
        return instance

class InstitutionSerializer(GenericSerializerMixin):
    class Meta:
        model = Institutions
        fields = ['name','acronym','country','id']

class AuthorSerializer(GenericSerializerMixin):
    #affiliations = InstitutionSerializer(read_only=True, many=True)
    affiliations = serializers.StringRelatedField(many=True, required=False)
    class Meta:
        model = Authors
        fields = ['first_name','last_name','email','orcid','affiliations','id']

class FundingStreamSerializer(GenericSerializerMixin):
    affiliation = serializers.StringRelatedField()
    
    class Meta:
        model = FundingStreams
        fields = ['name','affiliation','id']

class CitationSerializer(GenericSerializerMixin):
    primary = serializers.StringRelatedField()
    contacts = serializers.StringRelatedField(many=True)
    institutions = serializers.StringRelatedField(many=True)
    funders = serializers.StringRelatedField(many=True)

    class Meta:
        model = Citations
        fields = [
            'name', 'abstract', 'drs_url',
            'doi_url', 'rights', 'license',
            'primary', 'contacts', 'institutions',
            'funders', 'id'
        ]

