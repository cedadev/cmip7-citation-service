import requests
import json

citation = {
    'mip_era':'cmip7',
    "activity_id": "aerchemmip",
    "institution_id": "cccma",
    "source_id": "cnrm_esm2_1e",
    "experiment_id": "example_facet",
    'primary':json.dumps({
        'first_name':'Daniel',
        'last_name': 'Westwood',
        'orcid':'0009-0007-1866-5843',
        'email':"daniel.westwood@stfc.ac.uk"
    }),

}
temp_token = '7f50f7e592902b23bef32e9a630d040e6e229685'
temp_token = '69cb69a038897da333211f193b564102586889ba'
#SITE_URL = 'https://cmip7-citations-main.rancher2.130.246.130.221.nip.io'
SITE_URL = 'http://localhost:8000'

x = requests.post(f'{SITE_URL}/api/citations/', 
        data=citation, 
        headers={'Authorization':f'Token {temp_token}'},
        verify=False
    )
print(x)
print(x.content)