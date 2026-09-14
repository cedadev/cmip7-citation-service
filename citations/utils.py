import logging
import re
import esgvoc.api as ev
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


def add_new_references(data: dict, citation_types: list) -> tuple:
    # Only add references if they are not already present
    any_new = False
    for gr in obtain_all_references(data):
        new_ref = True
        for reftype in citation_types:

            ids = [ref['id'] for ref in data.get(reftype,[])]

            # Only add new references using this method.
            if gr["id"] in ids:
                new_ref = False

        # Add all CV references as 'cites'
        if new_ref:
            any_new = True
            if 'cites' not in data:
                data['cites'] = []
            data["cites"].append(gr)

    return data, any_new


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
            project_id=project_id, 
            collection_id=label, 
            term_id=data[facet].lower().replace('_','-') # Shift to dashes
        ) or ev.get_term_in_collection(
            project_id=project_id, 
            collection_id=label, 
            term_id=data[facet].lower().replace('-','_') # Shift to underscores
        )

        if not component:
            continue
        if not hasattr(component, "references"):
            continue

        # Under review based on ESGVOC changes.
        for ref in component.references:

            if not hasattr(ref,'doi'):
                continue
            
            if ref.doi in ref.citation:
                citeas = ref.citation
            else:
                citeas = f"{ref.citation} {ref.doi}"

            title = getattr(ref, "title", None) or re.search(
                r"^.*?\d{4}", ref.citation
            ).group(0)
            cites.append({"title": title, "citeas": citeas, "id": ref.doi})

    return cites