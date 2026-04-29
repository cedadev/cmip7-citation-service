import json

import requests


def add_party():

    party_info = {
        'email':'daniel.westwood@stfc.ac.uk',
    }

    temp_token = '69cb69a038897da333211f193b564102586889ba'

    print(
        requests.put('http://localhost:8000/api/party/430d35626d79e8bc0c4525855a173abe10fee261', 
            data=party_info, 
            headers={'Authorization':f'Token {temp_token}'}
        )
    )

if __name__ == '__main__':
    add_party()