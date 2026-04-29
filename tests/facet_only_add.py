import json

import requests

citation = {
    'mip_era':'cmip7',
    "activity_id": "aerchemmip",
    "institution_id": "cccma",
    "source_id": "cnrm_esm2_1e",
    "experiment_id": "example_facet",
    "domain_id": "cordex_uk",
    'primary':{
        'first_name':'Daniel',
        'last_name': 'Westwood',
        'orcid':'0009-0007-1866-5843',
        'email':"daniel.westwood@stfc.ac.uk"
    },

}
temp_token = '7f50f7e592902b23bef32e9a630d040e6e229685'
temp_token = '28bc6982e9c901052bf5c9c874f838a6b9c75a83'
#SITE_URL = 'https://cmip7-citations-main.rancher2.130.246.130.221.nip.io'
SITE_URL = 'http://localhost:8000'

x = requests.post(f'{SITE_URL}/api/citations/', 
        json=citation, 
        headers={'Authorization':f'Token {temp_token}'},
        verify=False
    )
print(x)
print(x.content)