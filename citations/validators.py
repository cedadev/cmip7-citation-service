from typing import Union

import requests
import xmltodict
from django.conf import settings
from django.core.exceptions import ValidationError

import logging
from citations.utils import logstream

try:
    import esgvoc.api as ev
except ImportError:
    ev = None

logger = logging.getLogger(__name__)
logger.addHandler(logstream)
logger.propagate = False


def validate_orcid(orcid: Union[str,None]):
    """
    Validate ORCID is either none or it exists"""

    if orcid is None:
        return

    r = xmltodict.parse(
        requests.get(
            f'https://pub.orcid.org/v3.0/expanded-search/?q=orcid%3A{orcid}'
        ).text
    )['expanded-search:expanded-search'].get('@num-found',"0")

    if r == "0":
        raise ValidationError(
            f"'{orcid}' does not appear in the ORCID registry"
        )
    
def validate_country(country: Union[str,None]):
    """
    Validate country is known or set as None
    """

    if country is None:
        return

    import pycountry

    try:
        _ = pycountry.countries.search_fuzzy(country)
    except LookupError:
        raise ValidationError(
            f'"{country}" returned no matches'
        )
    
def validate_component(
        component: str, 
        label: str, 
        requested: Union[str,None] = None, 
        raise_exception: bool = False,
        repo: str = settings.CV_REPO):
    """
    Check mip_era against CVs
    """

    if ev:
        project_id = 'CMIP7'
        if repo != settings.CV_REPO:
            project_id = 'CORDEX-CMIP6'

        logger.info(f'Validating {component} as {label} in {project_id} using ESGF Vocabs')
        term_result = ev.get_term_in_collection(term_id=component.lower(), project_id=project_id.lower(), collection_id=label.lower())
        if not bool(term_result):
            logger.error(f'{component} not found in ESGF Vocabs for {label} in {project_id}')
            raise ValidationError(f'{component} not a valid {label}')
        
        if requested:
            return getattr(term_result,requested,[])

    else:
        r = requests.get(f'{repo}/{label.lower()}/{component.lower()}.json')
        if str(r.status_code) != '200':
            if raise_exception:
                raise ValidationError(f'{component} not a valid {label}')
            else:
                return None
        
        if requested:
            return r.json()[requested]
    
def validate_cordex_facets(data: dict, raise_exceptions: bool = False):

    if settings.CORDEX_CV_REPO is None:
        raise ValueError('Misconfigured for CORDEX Facet validation')
    
    validate_component(data.get('mip_era').replace('CORDEX-',''), 'mip_era', 
                       raise_exception=raise_exceptions, repo=settings.CORDEX_CV_REPO)
    
    validate_component(data.get('activity_id'), 'activity_id', 
                       raise_exception=raise_exceptions, repo=settings.CORDEX_CV_REPO)
    
    validate_component(data.get('domain_id'), 'domain_id', 
                       raise_exception=raise_exceptions, repo=settings.CORDEX_CV_REPO)
    
    validate_component(data.get('institution_id'), 'institution_id', 
                       raise_exception=raise_exceptions, repo=settings.CORDEX_CV_REPO)
    
    validate_component(data.get('experiment_id'), 'driving_experiment_id', 
                       raise_exception=raise_exceptions, repo=settings.CORDEX_CV_REPO)
    
    validate_component(data.get('source_id'), 'source_id', 
                       raise_exception=raise_exceptions, repo=settings.CORDEX_CV_REPO)

def validate_cmip7_facets(data: dict, raise_exceptions: bool = False):

    if settings.CV_REPO is None:
        raise ValueError('Misconfigured for CMIP7 Facet validation')

    validate_component(data.get('mip_era'), 'mip_era', raise_exception=raise_exceptions)
    validate_component(data.get('experiment_id'), 'experiment',raise_exception=raise_exceptions)
    validate_component(data.get('institution_id'), 'institution',raise_exception=raise_exceptions)
    validate_component(data.get('source_id'), 'source',raise_exception=raise_exceptions)

    experiments = validate_component(data.get('activity_id'), 'activity', requested='experiments') or []
    if data.get('experiment_id') not in experiments:
        if raise_exceptions:
            raise ValidationError(f'{data.get('experiment_id')} not valid for {data.get('activity_id')}: Valid experiments are {experiments}')

def validate_title(title: str, raise_exceptions = False):
    """
    Validate title parameter for CMIP7 citation record
    """

    try:
        mip_era, activity_id, institution_id, source_id, experiment_id = title.split('.')
    except ValueError:
        if raise_exceptions:
            raise ValidationError('Title does not have all required components')
        return {}
    
    if settings.CV_REPO is not None:
        validate_component(mip_era, 'mip_era', raise_exception=raise_exceptions)
        validate_component(experiment_id, 'experiment',raise_exception=raise_exceptions)
        validate_component(institution_id, 'institution',raise_exception=raise_exceptions)
        validate_component(source_id, 'source',raise_exception=raise_exceptions)

        experiments = validate_component(activity_id, 'activity', requested='experiments') or []
        if experiment_id not in experiments:
            if raise_exceptions:
                raise ValidationError(f'{experiment_id} not valid for {activity_id}: Valid experiments are {experiments}')
            else:
                experiment_id = ''
        
    return {
        'mip_era':mip_era,
        'activity_id':activity_id,
        'institution_id':institution_id,
        'source_id':source_id,
        'experiment_id':experiment_id
    }