import requests


def add_party():

    party_info = {
        'first_name': 'Daniel',
        'last_name': 'Westwood',
        'orcid': '0009-0007-1866-5843',
        'email': 'daniel.westwood@stfc.ac.uk'
    }

    temp_token = '69cb69a038897da333211f193b564102586889ba'

    print(
        requests.post('http://localhost:8000/api/parties/', 
            data=party_info, 
            headers={'Authorization':f'Token {temp_token}'}
        )
    )

if __name__ == '__main__':
    add_party()