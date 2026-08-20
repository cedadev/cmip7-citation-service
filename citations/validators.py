import logging
from typing import Union

import requests
import xmltodict
from django.conf import settings
from django.core.exceptions import ValidationError

from citations.utils import logstream

try:
    import esgvoc.api as ev
except ImportError:
    ev = None

logger = logging.getLogger(__name__)
logger.addHandler(logstream)
logger.propagate = False


def validate_orcid(orcid: Union[str, None]):
    """
    Validate ORCID is either none or it exists"""

    if orcid is None:
        return

    r = xmltodict.parse(
        requests.get(
            f"https://pub.orcid.org/v3.0/expanded-search/?q=orcid%3A{orcid}"
        ).text
    )["expanded-search:expanded-search"].get("@num-found", "0")

    if r == "0":
        raise ValidationError(f"'{orcid}' does not appear in the ORCID registry")


def validate_country(country: Union[str, None]):
    """
    Validate country is known or set as None
    """

    if country is None:
        return

    import pycountry

    try:
        _ = pycountry.countries.search_fuzzy(country)
    except LookupError:
        raise ValidationError(f'"{country}" returned no matches')


def validate_project(
        project_id: str
    ) -> bool:

    if not ev:
        raise ValueError('API not defined - unable to perform validation')
    if project_id not in ev.get_all_projects():
        raise ValidationError(f"{project_id} not a valid project/collection in esgvoc")

def validate_component(
    component: str,
    label: str,
    project_id: str,
    requested: Union[str, None] = None,
    raise_exception: bool = False,
    repo: str = settings.CV_REPO,
) -> tuple:
    """
    Check project_id against CVs
    """

    if ev:

        logger.info(
            f"Validating {component} as {label} in {project_id} using ESGF Vocabs"
        )
        term_result = ev.get_term_in_collection(
            term_id=component.lower().replace('_','-'), # Shift to dashes
            project_id=project_id.lower(),
            collection_id=label.lower(),
        ) or ev.get_term_in_collection(
            term_id=component.lower().replace('-','_'), # Shift to underscores if no dashes.
            project_id=project_id.lower(),
            collection_id=label.lower(),
        )
        
        if not bool(term_result):
            logger.error(
                f"{component} not found in ESGF Vocabs for {label} in {project_id}"
            )
            v = ValidationError(f"{component} not a valid {label}")

            if raise_exception:
                raise v
            return False, component, v

        value = component
        if requested is not None:
            value = getattr(term_result, requested, [])
        return True, value, None

    else:
        r = requests.get(f"{repo}/{label.lower()}/{component.lower()}.json")
        if str(r.status_code) != "200":
            v = ValidationError(f"{component} not a valid {label}")
            if raise_exception:
                raise v
            return False, component, v

        value = component
        if requested is not None:
            value = r.json()[requested]
        return True, value, None
