from typing import Union

import requests
import xmltodict
from django.conf import settings
from django.core.exceptions import ValidationError


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
    
def validate_component(component: str, label: str, requested: Union[str,None] = None, raise_exception: bool = False):
    """
    Check mip_era against CVs
    """
    r = requests.get(f'{settings.CV_REPO}/{label}/{component}.json')
    if str(r.status_code) != '200':
        if raise_exception:
            raise ValidationError(f'{component} not a valid {label}')
        else:
            return None
    
    if requested:
        return r.json()[requested]
    
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
                raise ValidationError(f'{experiment_id} not valid for {activity_id}')
            else:
                experiment_id = ''
        
    return {
        'mip_era':mip_era,
        'activity_id':activity_id,
        'institution_id':institution_id,
        'source_id':source_id,
        'experiment_id':experiment_id
    }