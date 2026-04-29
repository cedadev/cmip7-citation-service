import json

import requests

temp_token = '7f50f7e592902b23bef32e9a630d040e6e229685'
temp_token = '69cb69a038897da333211f193b564102586889ba'
#SITE_URL = 'https://cmip7-citations-main.rancher2.130.246.130.221.nip.io'
SITE_URL = 'http://localhost:8000'

citation = {}
import httpx

with httpx.Client(verify=False) as client:
    print(
        client.delete(f'{SITE_URL}/api/citation/{citation["title"]}_{citation["version"]}',  
            headers={'Authorization':f'Token {temp_token}'},
        )
    )