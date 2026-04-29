import requests


def add_fs():

    fs_info = {
        'name': 'UKRI 2025-2026 Stream 2',
        'affiliation': 'University of York'
    }

    temp_token = '8b9377ef005b5fc883af2e88184b8b6275209063'

    print(
        requests.post('http://localhost:8000/api/fundings/', 
            data=fs_info, 
            headers={'Authorization':f'Token {temp_token}'}
        )
    )

if __name__ == '__main__':
    add_fs()