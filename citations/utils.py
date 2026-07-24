import logging
from typing import Union

from django.conf import settings
from citations.facet_mappings import ESGVOC_FACET_LABELS

if settings.DEBUG:
    logging.basicConfig(level=logging.DEBUG)
else:
    logging.basicConfig(level=logging.INFO)
logstream = logging.StreamHandler()

formatter = logging.Formatter("%(levelname)s [%(name)s]: %(message)s")
logstream.setFormatter(formatter)

def is_support_user(data: dict):
    if data.get('id','') == settings.SUPPORT_ID:
        return True
    if data['first_name'] == settings.SUPPORT_FIRSTNAME and data['last_name'] == settings.SUPPORT_LASTNAME:
        return True
    return False

def get_drs_url(data: dict) -> Union[str, None]:
    """
    Obtain the DRS URL expected for this record, given the set of search facets.
    """

    metagrid_url = getattr(settings, "METAGRID_URL",None)

    # No auto-DRS if no metagrid URL
    if not bool(metagrid_url):
        return ""

    # No auto-DRS if the mip era is not given
    if not bool(data.get("project_id")):
        return ""

    project_id = data["project_id"].lower()

    metagrid_base = f'{settings.METAGRID_URL}/search?project={project_id}+STAC&activeFacets=%7B"project_id"%3A"{project_id}"'

    queries = [metagrid_base]
    for facet in ESGVOC_FACET_LABELS[project_id].values():

        # No auto-DRS if any facet is missing
        if not bool(data.get(facet, False)):
            return ""

        queries.append(
            f'"{facet}"%3A"{data[facet]}"',
        )

    drs_url = "%2C".join(queries)

    return drs_url