import os
import json
import requests
import logging
from django.conf import settings
from citations.facet_mappings import ESGVOC_FACET_LABELS, STAC_LABELS, STAC_COLLECTIONS
from citations.utils import logstream

logger = logging.getLogger(__name__)
logger.addHandler(logstream)
logger.propagate = False


def get_stac_query(data: dict) -> dict:
    """
    Obtain the valid STAC query that should yield datasets for this record
    """

    project_id = data["project_id"].lower()
    
    query = {}
    for label, facet in ESGVOC_FACET_LABELS[project_id].items():
        if data.get(facet, None) is None:
            return False
        
        if facet == 'project_id':
            continue

        query[
            f'{project_id}:{STAC_LABELS.get(label,facet)}'
        ] = {'eq':data[facet]}

    query_url = f'{os.path.join(settings.STAC_API,'search')}?collections={STAC_COLLECTIONS[project_id]}'

    query_url += f'&query={json.dumps(query)}'

    # Remove whitespaces
    query_url = query_url.replace(' ','')
    return query_url


def resolve_stac_query(data: dict) -> bool:

    if not getattr(settings, "STAC_API", None):
        return False

    if not bool(data.get("project_id")):
        return False
    
    query_url = get_stac_query(data)

    logger.info(f'Querying STAC using: {query_url}')

    r = requests.get(query_url)

    if r.status_code != 200:
        return False
    
    if r.json()['numberMatched'] < 1:
        return False
    
    # Only return True if STAC query contains 1 or more items.
    return True