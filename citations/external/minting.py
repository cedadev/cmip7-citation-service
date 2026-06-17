import os
import base64
import logging
import json
from datetime import datetime

import requests
from django.conf import settings

from citations.utils import logstream, get_drs_url
from citations.facet_mappings import ESGVOC_FACET_LABELS, STAC_LABELS, STAC_COLLECTIONS

# from esgf_core_utils.models.kafka.consumer import KafkaConsumer

logger = logging.getLogger(__name__)
logger.addHandler(logstream)
logger.propagate = False


def get_ror_link(inst: str):
    """
    Fetch the unique ROR id link for an institution.
    """
    if inst is None:
        return None

    ROR_api = "https://api.ror.org/v2/organizations?query=" + "%20".join(
        inst.split(" ")
    )
    r = requests.get(ROR_api)
    if int(r.status_code) >= 300:
        print("Institute not found")
        return None

    resp = r.json()
    found = False
    inst_count = 0
    while not found and inst_count < 10:
        names = resp["items"][inst_count]["names"]
        for entry in names:
            if entry["value"] == inst:
                found = True
                break

        if not found:
            inst_count += 1

    if found:
        return resp["items"][inst_count]["id"]
    return None


def mint_doi_for_record(
    data: dict, publication_timestamp: str, id: str, return_citation: bool = False
) -> str:
    """
    Apply to mint a DOI via DataCite for the information in this record.

    Create the DOI request and send to DataCite. This includes assembling the DataCite-compliant JSON payload.
    """

    if not getattr(settings, "DATACITE_API_URL", None):
        return None

    creator_info = data["creators"]

    creators = []
    for creator in creator_info:

        affiliations = []
        for affil in creator.get("affiliations", []):
            affiliations.append(
                {
                    "affiliationIdentifier": get_ror_link(affil.get("name")),
                    "affiliationIdentifierScheme": "ROR",
                    "name": affil.get("name"),
                    "schemeUri": "https://ror.org/",
                }
            )

        creator_data = {
            "name": f"{creator['last_name']}, {creator['first_name']} {creator.get('middle_names', '')}",
            "affiliation": affiliations,
        }
        if creator.get("orcid"):
            creator_data["nameIdentifiers"] = [
                {
                    "schemeUri": "https://orcid.org",
                    "nameIdentifier": "https://orcid.org/" + creator["orcid"],
                    "nameIdentifierScheme": "ORCID",
                }
            ]
        creators.append(creator_data)

    funds = []
    for fund in data.get("funders", []):
        funds.append(
            {"awardTitle": fund.get("name"), "funderName": fund.get("affiliation")}
        )

    related_identifiers = []
    for reltype in ["cites", "is_cited_by", "is_referenced_by"]:
        for rel in data.get(reltype, []):
            related_identifiers.append(
                {
                    "relatedIdentifier": rel["id"],
                    "relatedIdentifierType": "URL",
                    "relationType": reltype.replace("_", " ").title().replace(" ", ""),
                }
            )

    yyyymmdd = publication_timestamp.split('T')[0].replace('-','')
    yyyy = yyyymmdd[:4]

    payload = {
        "data": {
            "type": "dois",
            "attributes": {
                "prefix": settings.DOI_PREFIX,
                "creators": creators,
                "titles": [
                    {
                        "lang": "en",
                        "title": f"ESGF-NG {data['title']} version {data['version']}",
                    }
                ],
                "publisher": {
                    "name": "STFC",
                    "publisherIdentifier": "https://ror.org/057g20z61",
                    "publisherIdentifierScheme": "ROR",
                    "schemeUri": "https://ror.org/",
                },
                "publicationYear": yyyy,  # Do we want this as a field in the citation service?
                "types": {"resourceTypeGeneral": "Text"},
                "url": settings.SERVICE_URL + "/citation/" + id,
                "version": data["version"],
                "rightsList": [],
                "fundingReferences": funds,
                "relatedIdentifiers": related_identifiers,
            },
        }
    }

    if "test" not in settings.DATACITE_API_URL:
        payload["attributes"]["event"] = "publish"

    logger.info(f"Sending Request to: {settings.DATACITE_API_URL}")

    if return_citation:
        return payload

    token = base64.b64encode(
        bytes(f"{settings.DATACITE_USERNAME}:{settings.DATACITE_PASSWORD}", "utf-8")
    ).decode("utf-8")

    headers = {
        "accept": "application/vnd.api+json",
        "content-type": "application/json",
        "authorization": f"Basic {token}",
    }

    r = requests.post(settings.DATACITE_API_URL, json=payload, headers=headers)

    if r.status_code >= 300:
        logger.error(f"DOI Minting Failed: {r.content}")
        return None

    return f"https://doi.org/{r.json()['data']['id']}"


def resolve_drs(drs_url: str | None) -> bool:
    """
    Resolve a DRS URL to check if data exists.

    This should return False if the DRS (Data Access) URL returns a 404 or
    some other response to indicate the data is not available. This function prevents
    DOIs being minted for records where the data is not yet accessible.
    """

    if not bool(drs_url):
        return False
    
    # Data Access Check for DRS URL here.
    return False

def resolve_stac_query(data: dict) -> bool:

    if not getattr(settings, "STAC_API", None):
        return False

    if not bool(data.get("mip_era")):
        return False
    
    project_id = data["mip_era"].lower()

    query = {}
    for label, facet in ESGVOC_FACET_LABELS[project_id].items():
        if data.get(facet, None) is None:
            return False
        
        if facet == 'mip_era':
            continue

        query[
            f'{project_id}:{STAC_LABELS.get(label,facet)}'
        ] = {'eq':data[facet]}

    query_url = f'{os.path.join(settings.STAC_API,'search')}?collections={STAC_COLLECTIONS[project_id]}'

    query_url += f'&query={json.dumps(query)}'

    # Remove whitespaces
    query_url = query_url.replace(' ','')
    logger.info(f'Querying STAC using: {query_url}')

    r = requests.get(query_url)

    if r.status_code != 200:
        return False
    
    if r.json()['numberMatched'] < 1:
        return False
    
    # Only return True if STAC query contains 1 or more items.
    return True

def publish_record(data: dict, id: str) -> str:
    """
    Apply to mint a DOI via DataCite for the information in this record.

    Assemble the ``published`` flag and set the publication year in the resulting data.
    """
    publication = {}

    drs_url = data.get("drs_url", "")
    if not bool(drs_url):
        drs_url = get_drs_url(data)

    if not resolve_drs(drs_url) and not resolve_stac_query(data):
        return False, {"published": False}

    pub_ts = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
    publication["doi_url"] = mint_doi_for_record(data, pub_ts, id=id)
    if not publication["doi_url"]:
        return False, {"published": False}

    publication["publication_timestamp"] = pub_ts

    return True, publication | {"published": True, "editable": False}
