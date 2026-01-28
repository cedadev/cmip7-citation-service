import requests

def add_party():

    party_info = {
        'first_name': 'Daniel',
        'last_name': 'Westwood',
        'orcid': '0009-0007-1866-5843',
        'email': 'daniel.westwood@ncas.ac.uk'
    }

    temp_token = '8b9377ef005b5fc883af2e88184b8b6275209063'

    print(
        requests.put('http://localhost:8000/api/party/430d35626d79e8bc0c4525855a173abe10fee261', 
            data=party_info, 
            headers={'Authorization':f'Token {temp_token}'}
        )
    )

if __name__ == '__main__':
    add_party()