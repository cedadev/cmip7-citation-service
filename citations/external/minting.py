from datetime import datetime

import requests
from django.conf import settings
from django.contrib import messages


def get_ror_link(inst: str):
    """
    Fetch the unique ROR id link for an institution.
    """
    if inst is None:
        return None
    
    ROR_api = 'https://api.ror.org/v2/organizations?query=' + '%20'.join(inst.split(' '))
    r = requests.get(ROR_api)
    if int(r.status_code) >= 300:
        print('Institute not found')
        return None

    resp = r.json()
    found = False
    inst_count = 0
    while not found and inst_count < 10:
        names = resp['items'][inst_count]['names']
        for entry in names:
            if entry['value'] == inst:
                found = True
                break

        if not found:
            inst_count += 1

    if found:
        return resp['items'][inst_count]['id']
    return None

def mint_doi_for_record(data: dict, publication_year: int) -> str:
    """
    Apply to mint a DOI via DataCite for the information in this record
    """

    creator_info = data['creators']

    creators = []
    for creator in creator_info:

        affiliations = []
        for affil in creator.get('affiliations', []):
            affiliations.append({
                'affiliationIdentifier': get_ror_link(affil.get('name')),
                'affiliationIdentifierScheme': 'ROR',
                'name': affil.get('name'),
                'schemeUri': 'https://ror.org/'
            })

        creator_data = {
            'name': f"{creator['last_name']}, {creator['first_name']} {creator.get('middle_names', '')}",
            'affiliation': affiliations,
        }
        if creator.get('orcid'):
            creator_data['nameIdentifiers'] = [{
                "schemeUri": "https://orcid.org",
                "nameIdentifier": "https://orcid.org/" + creator['orcid'],
                "nameIdentifierScheme": "ORCID"
            }]
        creators.append(creator_data)

    funds = []
    for fund in data.get('funders', []):
        funds.append({
            "awardTitle": fund.get('name'),
            "funderName": fund.get('affiliation')
        })

    related_identifiers = []
    for reltype in ['cites','is_cited_by','is_referenced_by']:
        for rel in data.get(reltype, []):
            related_identifiers.append({
                "relatedIdentifier": rel['id'],
                "relationType": reltype.replace('_', ' ').title().replace(' ', '')
            })

    doi_unique = ''
    doi_prefix = '' # settings.DOI_PREFIX

    payload = {
        "data": {
            "type":"dois",
            "attributes":{
                "event" : "publish", # For live publication
                "doi": f'{doi_prefix}/ESGF/CMIP7.{doi_unique}',
                "creators": creators,
                "titles":[
                    {
                        "lang": "en",
                        "title": f"ESGF-NG CMIP7 {data['title']}"
                    }
                ],
                "publisher": {
                    "name": "STFC",
                    "publisherIdentifier":"https://ror.org/057g20z61",
                    "publisherIdentifierScheme":"ROR",
                    "schemeUri": "https://ror.org/"
                },
                "publicationYear": publication_year, # Do we want this as a field in the citation service?
                "types": {
                    "resourceTypeGeneral": "Text"
                },
                "url": settings.SERVICE_URL + '/citation/' + data['id'],
                "version": data['version'],
                "rightsList": [],
                "fundingReferences": funds,
                "relatedIdentifiers": related_identifiers
            }
        }
    }

    if settings.DATACITE_API_URL:
        r = requests.post(
            settings.DATACITE_API_URL,
            json=payload,
            auth=(settings.DATACITE_USERNAME, settings.DATACITE_PASSWORD)
        )

        if r.status_code >= 300:
            return None
        
        return r.json()['data']['id']
    
    # Placeholder implementation - replace with actual minting logic
    return f"https://doi.org/10.1234/{data.get('id', 'unknown')}"

def resolve_drs(drs_url: str):
    """
    Resolve a DRS URL to check if data exists
    """
    # Placeholder implementation - replace with actual resolution logic
    return True

def publish_record(data: dict) -> str:
    """
    Apply to mint a DOI via DataCite for the information in this record
    """
    publication = {}

    if not resolve_drs(data.get('drs_url', '')):
        return False, {'published':False}

    pub_yr = int(datetime.now().year)
    publication['doi_url'] = mint_doi_for_record(data, pub_yr)
    if not publication['doi_url']:
        return False, {'published':False}
    
    publication['publication_year'] = pub_yr


    return True, publication | {'published': True}