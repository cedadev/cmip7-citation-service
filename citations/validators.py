from django.core.exceptions import ValidationError
import requests
import xmltodict
from typing import Union

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