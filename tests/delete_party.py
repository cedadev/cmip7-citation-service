import json

import requests

temp_token = '28bc6982e9c901052bf5c9c874f838a6b9c75a83'
#SITE_URL = 'https://cmip7-citations-main.rancher2.130.246.130.221.nip.io'
SITE_URL = 'http://localhost:8000'

citation = {}
import httpx

with httpx.Client(verify=False) as client:
    print(
        client.delete(f'{SITE_URL}/api/party/116414370a2444f4ccfbadf600b53518a3edf769',  
            headers={'Authorization':f'Token {temp_token}'},
        )
    )