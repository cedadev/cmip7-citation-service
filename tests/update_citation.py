import json

import requests

citation = {
    'funders': json.dumps([
        {'name': 'UKRI sect 3'},
        {'name': 'UKRI sect 2'}
    ]),

}
temp_token = '7f50f7e592902b23bef32e9a630d040e6e229685'
temp_token = '69cb69a038897da333211f193b564102586889ba'
#SITE_URL = 'https://cmip7-citations-main.rancher2.130.246.130.221.nip.io'
SITE_URL = 'http://localhost:8000'

print(
    requests.put(f'{SITE_URL}/api/citation/cmip7.aerchemmip.cccma.cnrm_esm2_1e.esm-scen7-h-aer_v1', 
        data=citation, 
        headers={'Authorization':f'Token {temp_token}'},
        verify=False
    )
)