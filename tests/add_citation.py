import json

import httpx

citation = {
    'title':'cmip7.aerchemmip.cccmb.cnrm_esm2_1e.esm-scen7-h-aob',
    "abstract":"This is a test record, created by Daniel Westwood at CEDA",
    "drs_url":"",
    "publish_on_save": True,
    "rights":"Example section relating to Rights",
    "license":"License for this dataset",
    'primary':{
        'first_name':'Daniel',
        'last_name': 'Westwood',
        'orcid':'0009-0007-1866-5843',
        'email':"daniel.westwood@stfc.ac.uk"
    },
    'contacts':[
        {
            'first_name':'David',
            'last_name': 'Westwood',
            'orcid':'0009-0007-1866-5843',
            'email':"daniel.westwood@stfc.ac.uk"
        },{
            'first_name':'Jesse',
            'last_name': 'Alexander',
            'orcid':'0009-0006-2877-3197',
        }
    ],
    'funders': [{
        'name': 'UKRI sect 3',
        'affiliation': 'York University'
    }],
    'institutions': [{
        'name': 'York University'
    }],
    'cites':[{
        'title':'A very long way to a small angry title, with additional bits and a lengthy description (2026)',
        'citeas':"A very long way to a small angry title, with additional bits and a lengthy description (2026). Westwood, D.; Alexander, J.; Sykes, E. doi.org/1j2rthf", 'id':'doi.org/1j2rthf'
    }]

}
temp_token = '28bc6982e9c901052bf5c9c874f838a6b9c75a83'
#SITE_URL = 'https://cmip7-citations-main.rancher2.130.246.130.221.nip.io'
SITE_URL = 'http://localhost:8000'

with httpx.Client(verify=False) as client:
    print(
        client.post(f'{SITE_URL}/api/citations/', 
            json=citation, 
            headers={'Authorization':f'Token {temp_token}'},
        )
    )