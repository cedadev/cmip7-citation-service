import copy
import hashlib
import json
import logging
import re
from typing import Union
from datetime import datetime

import requests
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from rest_framework import serializers
from rest_framework.exceptions import MethodNotAllowed

from citations.consumer.write import create_instance, update_instance
from citations.external import publish_record
from citations.facet_mappings import (
    BACKUP_REPOS,
    ESGVOC_FACET_LABELS,
    ESGVOC_TITLE_LABELS,
    FACET_ABSTRACT_DESCRIPTIONS,
)
from citations.models import (
    Citations,
    CitationParty,
    FundingStreams,
    Institutions,
    Parties,
    References,
    FailedRequests,
    extract_from_orcid,
    locate_institute,
)
from citations.utils import logstream
from citations.validators import validate_component, validate_project

try:
    import esgvoc.api as ev
except ImportError:
    ev = None

logger = logging.getLogger(__name__)
logger.addHandler(logstream)
logger.propagate = False


def mint_doi_for_data(data: dict, id: str) -> dict | None:
    """
    'Data' is the partially serialized content for the record to be published.

    - Expand all creators (proper serialization)
    - Expand all funders
    - Expand all references
    - Send data to publish record

    This function is considered a 'core' function because it relies on access
    to the models of this application.
    """
    data = copy.deepcopy(data)

    if data['primary_id'] == settings.SUPPORT_ID:
        # Not allowed
        raise ValidationError('Unable to mint DOI for record with "Citation Support" as primary author.')

    creators = [
        PartiesSerializer(instance=Parties.objects.get(pk=data["primary_id"])).get_data()
    ] + [
        PartiesSerializer(instance=Parties.objects.get(pk=pk)).get_data()
        for pk in data["contacts"]
    ]

    data["creators"] = creators

    funders = [
        FundingStreamsSerializer(instance=FundingStreams.objects.get(pk=pk)).get_data()
        for pk in data["funders"]
    ]

    data["funders"] = funders

    for reltype in ["cites", "is_cited_by", "is_referenced_by"]:
        data[reltype] = [
            ReferencesSerializer(instance=References.objects.get(pk=pk)).get_data()
            for pk in data.get(reltype, [])
        ]

    status, pubdata = publish_record(data, id=id)
    if status:
        return pubdata


def institution_mappings(institution_id: str, project_id: str = "cmip7") -> str:
    """
    Apply known institution mappings given the institution_id which is most likely the acronym.
    """

    if not ev:
        # No ESGVOC - use either mapping or return basic info.
        try:
            mappings = requests.get(settings.INSTITUTION_MAPPINGS_URL).json()
            return mappings[institution_id.lower()]
        except Exception:
            return {"name": institution_id, "acronym": institution_id}

    esgvoc_institution = {v: k for k, v in ESGVOC_FACET_LABELS.get(project_id, {}).items()}.get(
        "institution_id"
    )

    if not esgvoc_institution:
        logger.info("Institution not defined or project ID not known")
        return {}

    # Get the institution from esgvoc
    component = ev.get_term_in_collection(
        project_id=project_id, collection_id="institution", term_id=institution_id
    ) or ev.get_term_in_collection(
        project_id=project_id,
        collection_id="institution",
        term_id=institution_id.lower(),
    )

    data = {"name": institution_id, "acronym": institution_id}
    if component:

        data.update(
            {
                "name": getattr(component, "description", institution_id),
                "acronym": getattr(component, "acronyms", [institution_id])[0],
            }
        )

        country = None
        try:
            country = component.members[0].location[0].country
        except Exception as e:
            pass

        if country:
            data.update({"country": country})
    return data


def title_from_facets(
    data: dict, raise_exceptions: bool = True
) -> tuple: # valid, title, response
    """
    Validate by generating the expected title from the facets.

    Facet title generation is `project_id` specific. If the `project_id` is not contained
    in the data, this function should not be run, but will return a None value."""

    if not bool(data.get("project_id")):
        v = ValidationError('Missing "project_id"')
        if raise_exceptions:
            raise v
        return False, '', v

    missing = []

    project_id = data["project_id"].lower()

    try:
        validate_project(project_id)
    except Exception as e:
        if raise_exceptions:
            raise e
        return False, '', e

    invalids = []

    for label, facet in ESGVOC_FACET_LABELS[project_id].items():

        if not data.get(facet, False):
            missing.append(facet)
            continue

        if facet == 'project_id':
            # No longer validating project_id - this is validated separately 
            # as the project ID with every query, as well as above.
            continue

        status, component, _ = validate_component(
            data.get(facet).lower(),
            label,
            project_id=project_id,
            raise_exception=raise_exceptions,
            repo=BACKUP_REPOS.get(project_id),
        )
        if not status:
            invalids.append(f'{label}={component}')

    pseudo_title = ".".join([data.get(facet,'<MISSING>') for facet in ESGVOC_TITLE_LABELS.get(project_id)])

    if invalids:
        v = ValidationError(f'The following combinations are not valid: {", ".join(invalids)}')
        if raise_exceptions:
            raise v
        return False, pseudo_title, v

    if len(missing) > 0:
        v = ValidationError(f'Missing components: {missing}')
        if raise_exceptions:
            raise v
        return False, pseudo_title, v

    if project_id == "cmip7":

        status, component, response = validate_component(
            data.get("activity_id"),
            "activity",
            project_id=project_id,
            requested="experiments",
        )
        if not status:
            if raise_exceptions:
                raise response
            return False, pseudo_title, response

        experiments = (
            component
            or []
        )
        if data.get("experiment_id").lower() not in experiments:
            v = ValidationError(
                f"{data.get('experiment_id')} not valid for {data.get('activity_id')}: Valid experiments are {experiments}"
            )
            if raise_exceptions:
                raise v
            return False, pseudo_title, v

    return True, pseudo_title, None


def obtain_all_references(data: dict) -> dict:
    """
    Obtain Citation references from the EMD (ESGVOC)

    Prevent adding a reference if it already exists.
    """

    if not ev:
        return {}

    project_id = data.get("project_id").lower()

    cites = []
    for label, facet in ESGVOC_FACET_LABELS[project_id].items():
        component = ev.get_term_in_collection(
            project_id=project_id, collection_id=label, term_id=data[facet].lower()
        )

        if not component:
            continue
        if not hasattr(component, "references"):
            continue

        for ref in component.references:

            if ref.doi in ref.citation:
                citeas = ref.citation
            else:
                citeas = f"{ref.citation} {ref.doi}"

            title = getattr(ref, "title", None) or re.search(
                r"^.*?\d{4}", ref.citation
            ).group(0)
            cites.append({"title": title, "citeas": citeas, "id": ref.doi})

    return cites


def assemble_license_info(data: dict) -> str:
    """
    Determine the paragraph of text to use for the license.
    """
    license = []
    if hasattr(settings, "GENERAL_INFO"):
        license += settings.GENERAL_INFO.split(".")
    if hasattr(settings, "CITATION_GUIDANCE"):
        license += settings.CITATION_GUIDANCE.split(".")

    license.append(f'Published under {data["rights"]}.')

    license = [lp for lp in license if lp.replace("\n", "")]

    return ". ".join(license).replace("\n", "")


def abstract_from_esgvoc(data: dict):
    """
    Determine the paragraph of abstract text from esgvoc parameters.
    """

    # No auto-abstract if no ESGVOC integration.
    if not ev:
        return ""

    project_id = data.get("project_id").lower()

    facet_labels = ESGVOC_FACET_LABELS[project_id]

    abstract = []
    for label, facet_desc in FACET_ABSTRACT_DESCRIPTIONS.items():
        if label not in facet_labels:
            continue

        facet = facet_labels[label]
        if not bool(data.get(facet)):
            continue

        entry = []
        component = ev.get_term_in_collection(
            project_id=project_id, collection_id=label, term_id=data[facet].lower()
        )
        print(component)

        description = getattr(component, "description", data[facet])
        if not bool(description):
            description = f'{facet}: {data[facet]}'

        entry.append(description)

        if getattr(component, "labels", None):
            entry.append(",".join(component.labels))

        if isinstance(facet_desc, list):
            # Rendering institution description
            descs = facet_desc
            abstract.append(
                descs[0]
                + " - ".join(entry)
                + descs[1]
                + data["source_id"]
                + descs[2]
                + data["experiment_id"]
                + descs[3]
            )
        else:
            abstract.append(facet_desc + " - ".join(entry))

    if abstract and hasattr(settings, "GENERAL_INFO"):
        abstract += [settings.GENERAL_INFO]

    if abstract and hasattr(settings, "CEDA_INFO"):
        abstract += [settings.CEDA_INFO]

    return "\n\n".join([a.replace("\n", "") for a in abstract])


def chain_new_objects(
    data: dict,
    serializer: serializers.ModelSerializer,
    model: type[models.Model],
    filter_kwargs: list,
    optionals: list = None,
    allow_update: bool = False,
) -> str:
    """
    Create new model instances if required, or return the ID of the existing instance.

    This includes locating the existing record based on some filter kwargs (normally just the ID)
    to identify the existing instance.
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
        inst_pk = serial.instance["id"]
    else:
        # Update the existing record with new data - if allowed
        instance = instance[0]
        serial = serializer(data=data, instance=instance)

        serial.is_valid(raise_exception=True)
        update = False

        # Some record types cannot be updated using this mechanism.
        if allow_update:
            for k, v in data.items():
                if v != getattr(instance, k):
                    update = True

        # Save the record only if an update is required - will cut down on
        # extra kafka messages if that is in place.
        if update:
            serial.save()
        inst_pk = serial.validated_data.get("id", instance.pk)

    # Returns the id of the record
    # NOTE: If the internal kafka queue is set up, it is possible the ID will be for a record that does not yet exist.
    return inst_pk


class GenericSerializerMixin(serializers.ModelSerializer):

    def get_data(self):
        return self.data

    def to_internal_value(self, data):

        data = data.copy()
        if self.context.get("view"):
            if "pk" in self.context["view"].kwargs:
                data["id"] = self.context["view"].kwargs["pk"]

        return data

    def filter_data(self, validated_data: dict) -> dict:
        """
        Filter out unrecognised parameters.

        Also runs the `fill_data_parameters` method to auto-generate content.
        """
        filtered_data = {}
        validated_data = self.fill_data_parameters(validated_data)
        for k in list(validated_data.keys()):
            if (
                k in self.Meta.fields
                or k.replace("_id", "") in self.Meta.id_relations
                or k in self.Meta.internal_fields
            ):
                filtered_data[k] = validated_data.get(k, None)

        return filtered_data

    def replace_id_relations(self, validated_data: dict) -> dict:
        """
        Replace relations like `primary` in the citations model with `primary_id`
        """

        for k in getattr(self.Meta, "id_relations", []):
            if k in validated_data:
                validated_data[k + "_id"] = validated_data.pop(k)
        return validated_data

    def create(self, validated_data):
        """
        Create and return a model instance given validated data.
        """

        publish: bool = validated_data.pop("publish", False)
        user_id: str = validated_data.pop("user_id", "anon")

        filtered_data = self.filter_data(validated_data)

        # Check for required fields
        for k in self.Meta.required_fields:
            if k in getattr(self.Meta, "id_relations", []):
                if k + "_id" not in filtered_data:
                    raise MethodNotAllowed(f'Submission without "{k}" field')
                continue

            if (
                k not in filtered_data
                and getattr(self.Meta, "field_mappings", dict()).get(k)
                not in filtered_data
            ):
                raise MethodNotAllowed(f'Submission without "{k}" field')

        # Determine ID of specific record to be created
        pk = filtered_data[self.Meta.model._meta.pk.name]

        filtered_data = self.replace_id_relations(filtered_data)

        # If trying to create an existing record, switch to updating it.
        if self.Meta.model.objects.filter(pk=pk):
            return self.update(
                self.Meta.model.objects.get(pk=pk), filtered_data, publish=publish
            )

        # Run publication (DOI Minting workflow)
        if publish:
            pubdata = mint_doi_for_data(filtered_data, id=pk)
            if isinstance(pubdata, dict):
                filtered_data.update(pubdata)

        # Use Kafka-enabled instance creation
        create_instance(
            self.Meta.model,
            user=user_id,
            update_handler=handle_update,
            required_fields=self.Meta.required_fields,
            **filtered_data,
        )
        return filtered_data

    def update(self, instance, validated_data: dict):
        """
        Update and return an existing instance, given the validated data.
        """

        publish: bool = validated_data.pop("publish", False)
        user_id: str = validated_data.pop("user_id", "anon")

        filtered_data = self.filter_data(validated_data)
        filtered_data = self.replace_id_relations(filtered_data)
        id = filtered_data.pop("id", None)

        if len(filtered_data.keys()) == 0:
            raise MethodNotAllowed("No updates supplied")

        # Check attempts to change id-related fields that are immutable.
        for field in getattr(self.Meta, "immutable_fields", []):
            if filtered_data.get(field) != getattr(
                instance, field
            ) and filtered_data.get(field, None):
                raise MethodNotAllowed(f'The field "{field}" is immutable')

        # Run publication (DOI Minting workflow)
        if publish:
            pubdata = mint_doi_for_data(filtered_data, id=id)
            if isinstance(pubdata, dict):
                filtered_data.update(pubdata)

        # Use Kafka-enabled instance updating
        update_instance(
            self.Meta.model,
            user=user_id,
            update_handler=handle_update,
            id=instance.id,
            **filtered_data,
        )
        return filtered_data


class InstitutionsSerializer(GenericSerializerMixin):
    class Meta:
        model = Institutions
        required_fields = ["name"]
        fields = ["name", "acronym", "country", "id"]
        relations = []
        internal_fields = []

    def fill_data_parameters(self, data):
        """
        Auto-fill content into the data dict.
        """

        # Only ID provided - fill values from ROR API calls
        if not data.get("acronym", None) and not data.get("country", None):
            data.update(locate_institute(data["name"]))

        data["id"] = hashlib.sha1(data["name"].encode()).hexdigest()
        return data


class FailedRequestsSerializer(GenericSerializerMixin):
    class Meta:
        model = FailedRequests
        required_fields = ['id', 'reason']
        fields = required_fields

    def fill_data_parameters(self, data):
        return data

class PartiesSerializer(GenericSerializerMixin):
    affiliations = InstitutionsSerializer(required=False, many=True)

    class Meta:
        model = Parties
        required_fields = ["first_name", "last_name"]
        immutable_fields = ["first_name", "last_name", "middle_names"]
        fields = immutable_fields + ["email", "orcid", "affiliations", "id"]
        relations = ["affiliations"]
        internal_fields = []

    def fill_data_parameters(self, data):
        """
        Auto-fill content into the data dict.
        """

        # Pull information from ORCID
        affiliation_data = []
        if data.get("orcid", None):
            affiliation_data += extract_from_orcid(data["orcid"])

        if data.get("affiliations", None) is not None:
            # Properly connect non-blank affiliations
            affiliation_data += json.loads(data.pop("affiliations")[0])

        if not isinstance(affiliation_data, list):
            affiliation_data = [affiliation_data]

        # Create new institutions from the affiliations for this Author/Party
        if len(affiliation_data) > 0:
            data["affiliations"] = [
                chain_new_objects(
                    {"name": a},
                    InstitutionsSerializer,
                    Institutions,
                    filter_kwargs={"name": a},
                )
                for a in affiliation_data
            ]

        if "id" not in data:
            # Add ID from hashed version of all names
            naming_hash = (
                data["first_name"]
                + data.get("middle_names", "")
                + data.get("last_name")
            )
            party_id = hashlib.sha1(naming_hash.encode()).hexdigest()

            data["id"] = party_id
        return data


class FundingStreamsSerializer(GenericSerializerMixin):
    affiliation = serializers.StringRelatedField(required=False)

    class Meta:
        model = FundingStreams
        required_fields = ["name"]
        fields = ["name", "affiliation", "id"]
        relations = []
        id_relations = ["affiliation"]
        internal_fields = []

    def fill_data_parameters(self, data):
        """
        Auto-fill content into the data dict.
        """

        if "affiliation" in data:
            affiliation = data.pop("affiliation")

            data["affiliation_id"] = chain_new_objects(
                {"name": affiliation},
                InstitutionsSerializer,
                Institutions,
                filter_kwargs={"name": affiliation},
            )

        if "id" not in data:
            data["id"] = hashlib.sha1(data["name"].encode()).hexdigest()

        return data


class ReferencesSerializer(GenericSerializerMixin):

    class Meta:
        model = References
        fields = ["title", "citeas", "id"]
        required_fields = ["id"]
        relations = []
        id_relations = []
        field_mappings = {"DOI": "id"}
        internal_fields = []

    def fill_data_parameters(self, data):
        """
        No data filling for references
        """
        return data


class CitationsSerializer(GenericSerializerMixin):
    primary = PartiesSerializer(required=False)
    contacts = PartiesSerializer(required=False, many=True)
    institutions = InstitutionsSerializer(required=False, many=True)
    funders = FundingStreamsSerializer(required=False, many=True)
    is_cited_by = ReferencesSerializer(required=False, many=True)
    is_referenced_by = ReferencesSerializer(required=False, many=True)
    cites = ReferencesSerializer(required=False, many=True)

    class Meta:
        model = Citations
        citation_types = ["is_cited_by", "is_referenced_by", "cites"]

        # Core Facet Labels from the Database
        fields = [
            "title",
            "abstract",
            "drs_url",
            "doi_url",
            "rights",
            "license",
            "primary",
            "contacts",
            "institutions",
            "funders",
            "id",
            "version",
            "publication_timestamp",
            "project_id",
            "activity_id",
            "domain_id",
            "institution_id",
            "source_id",
            "experiment_id",
            "cites",
            "is_cited_by",
            "is_referenced_by",
        ]
        required_fields = ["title", "version", "primary"]
        non_replicating_fields = ["experiment_id", "doi_url", "publication_timestamp"]
        id_relations = ["primary"]
        insert_order_relations = ["contacts"]

        relations = [
            "contacts",
            "institutions",
            "funders",
            "is_cited_by",
            "is_referenced_by",
            "cites",
        ]
        internal_fields = ["editable", "published"]

    def get_data(self):
        data = dict(self.data)
        data['contacts'] = self.get_contacts()
        return data

    def get_contacts(self):
        contact_relations = CitationParty.objects.filter(citation=self.instance)
        return [PartiesSerializer(c.party).get_data() for c in contact_relations]

    def _set_order(self, instance, contacts):

        try:
            for pos, field in enumerate(contacts):
                c = CitationParty.objects.filter(
                    citation=instance,
                    party=Parties.objects.get(id=field),
                )
                if c:
                    c = c[0]
                    c.position = pos
                else:
                    c = CitationParty.objects.create(
                        citation=instance,
                        party=Parties.objects.get(id=field),
                        position=pos
                    )
                c.save()
        except Exception as e:
            print(e)

    def create(self, validated_data):
        """
        Apply extra validation to the citation record.

        This validates the ``search_facets`` if they have been provided to this record.
        """

        # Enforces valid facets for all records - but don't have to match title structure.
        if "project_id" in validated_data:

            # Validate by assembling expected title - if the search facets are provided.
            _, title, _ = title_from_facets(validated_data, raise_exceptions=True)

            if not bool(validated_data.get("title", False)):
                if not title:
                    raise ValidationError(
                        "Missing the `project_id` facet and no other title provided."
                    )
                elif isinstance(title, list):
                    raise ValidationError(
                        f"Missing facets: {title} - unable to generate title and no title provided."
                    )
                validated_data["title"] = title

        filtered_data = super().create(validated_data)

        # Ensure correct ordering - parties only
        instance = Citations.objects.get(id=filtered_data['id'])
        self._set_order(instance, filtered_data.get('contacts',[]))

        return filtered_data

    def update(self, instance, validated_data: dict):

        filtered_data = super().update(instance, validated_data)
        self._set_order(instance, filtered_data.get('contacts',[]))

        return filtered_data

    def fill_data_parameters(self, data: dict):
        """
        Update the data in a POST request.

        Locate or create references based on the provided information.
        """

        # Only add references if they are not already present
        for gr in obtain_all_references(data):
            new_ref = True
            for reftype in self.Meta.citation_types:
                if gr["id"] in data.get(reftype,[]):
                    new_ref = False
            if new_ref:
                if 'cites' not in data:
                    data['cites'] = []
                data["cites"].append(gr)

        # Auto-fill from ESGVOC
        if not bool(data.get("abstract")):
            data["abstract"] = abstract_from_esgvoc(data)
        if not bool(data.get("rights")):
            data["rights"] = settings.DEFAULT_RIGHTS  # 'CC-BY-4.0' SPDX identifier
        if not bool(data.get("license")):
            data["license"] = assemble_license_info(data)

        # Chain create institution
        if data.get("institution_id"):
            # Create new institution as below, and add to the main affiliated institutions

            inst_data = institution_mappings(data["institution_id"], data['project_id'].lower())

            institution = chain_new_objects(
                inst_data,
                InstitutionsSerializer,
                Institutions,
                filter_kwargs={"name": inst_data["name"]},
                allow_update=True,
            )
            if "institutions" not in data:
                data["institutions"] = []

            data["institutions"].append(institution)

        if data.get("version") is None and data.get("id") is None:

            # Version is auto-assigned
            version = len(self.Meta.model.objects.filter(title=data["title"])) + 1
            data["version"] = version

            # Identifier is auto-assigned
            id = data["title"] + "_v" + str(data["version"])
            data["id"] = id

        optional_party = list(
            set(PartiesSerializer.Meta.immutable_fields)
            - set(PartiesSerializer.Meta.required_fields)
        )
        # Unpack primaries, contacts
        if data.get("primary"):
            primary = data.pop("primary")
            if isinstance(primary, dict):
                # This does not correctly create institution objects
                search_primary = chain_new_objects(
                    primary,
                    PartiesSerializer,
                    Parties,
                    filter_kwargs=PartiesSerializer.Meta.required_fields,
                    optionals=optional_party,
                )
                primary = search_primary
            data["primary_id"] = primary

        if data.get("contacts"):
            contacts = []
            for contact in data.pop("contacts"):
                if isinstance(contact, dict):
                    search_contact = chain_new_objects(
                        contact,
                        PartiesSerializer,
                        Parties,
                        filter_kwargs=PartiesSerializer.Meta.required_fields,
                        optionals=optional_party,
                    )
                    contacts.append(search_contact)
                else:
                    contacts.append(contact)
            data["contacts"] = contacts

        # Unpack funders
        if data.get("funders"):
            funders = []
            for funder in data.pop("funders"):
                if isinstance(funder, dict):
                    search_funder = chain_new_objects(
                        funder,
                        FundingStreamsSerializer,
                        FundingStreams,
                        filter_kwargs=FundingStreamsSerializer.Meta.required_fields,
                    )
                    funders.append(search_funder)
                else:
                    funders.append(funder)
            data["funders"] = funders

        # Unpack institutions
        if data.get("institutions"):
            institutions = []
            for institution in data.pop("institutions"):
                if isinstance(institution, dict):
                    search_institution = chain_new_objects(
                        institution,
                        InstitutionsSerializer,
                        Institutions,
                        filter_kwargs=InstitutionsSerializer.Meta.required_fields,
                    )
                    institutions.append(search_institution)
                else:
                    institutions.append(institution)
            data["institutions"] = institutions

        # Unpack references - obtained via ESGVOC or UI
        for citation_type in self.Meta.citation_types:
            if not data.get(citation_type):
                continue
            references = []
            for ref in data.pop(citation_type):
                if isinstance(ref, dict):
                    reference = chain_new_objects(
                        ref,
                        ReferencesSerializer,
                        References,
                        filter_kwargs=ReferencesSerializer.Meta.required_fields,
                        allow_update=True,
                    )
                    references.append(reference)
                else:
                    references.append(ref)
            data[citation_type] = references

        data["published"] = False
        if data.get("doi_url", None):
            data["published"] = True

            # If a record contains a DOI but no publication_timestamp 
            # it was not published by the citation service, thus the 
            # publication timestamp is generated.
            
            if not bool(data.get('publication_timestamp')):
                data["publication_timestamp"] = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')

        return data


dj_tables = {
    "citations": Citations,
    "institutions": Institutions,
    "fundingstreams": FundingStreams,
    "parties": Parties,
    "references": References,
}

dj_serializers = {
    "citations": CitationsSerializer,
    "institutions": InstitutionsSerializer,
    "fundingstreams": FundingStreamsSerializer,
    "parties": PartiesSerializer,
    "references": ReferencesSerializer,
}


def handle_update(table: str, method: str, content: dict):
    """
    Handle ANY ORM Request updates here.

    This function is passed to the Kafka update system, and will be called directly
    if the Kafka Internal Queue is disabled."""

    model = dj_tables[table.lower()]
    serializer = dj_serializers[table.lower()]
    pk = model._meta.pk.name

    match method:
        case "create":
            instance = model.objects.create(
                **{
                    c: v
                    for c, v in content.items()
                    if c not in serializer.Meta.relations
                }
            )
            for r in serializer.Meta.relations:
                try:
                    if r in content:
                        getattr(instance, r).set(content[r])
                except Exception as e:
                    print(e)
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
