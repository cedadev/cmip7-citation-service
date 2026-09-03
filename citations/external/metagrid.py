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


def get_metagrid_query(data: dict) -> dict:
    """
    Obtain the valid STAC query that should yield datasets for this record
    """

    if not hasattr(settings,'METAGRID_URL'):
        return False

    project_id = data["project_id"].lower()
    
    query = []
    for facet in ESGVOC_FACET_LABELS[project_id].values():
        if data.get(facet, None) is None:
            return False
        
        if facet == 'project_id':
            continue

        query.append(
            f'%22{facet}%22%3A%22{data[facet]}%22')

    query_url = f'{os.path.join(settings.METAGRID_URL,'search')}?project={STAC_COLLECTIONS[project_id]}'

    query_url += f'&activeFacets=%7B{"%2C".join(query)}%7D'

    # Remove whitespaces
    query_url = query_url.replace(' ','')
    return query_url

# https://metagrid-ceda.east.esgf.io/search?project=CMIP7&activeFacets=%7B%22institution_id%22%3A%22CCCma%22%2C%22source_id%22%3A%22CanESM5-1%22%2C%22experiment_id%22%3A%221pctCO2%22%2C%22activity_id%22%3A%22CMIP%22%7D

