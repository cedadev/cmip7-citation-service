import requests
import json

citation = {
    'title':'cmip7.aerchemmip.cccma.canesm6-mr.esm-scen7-h-aer',
    'version':1,
    "abstract":"This is a test record, created by Daniel Westwood at CEDA",
    "drs_url":"https://google.com",
    "rights":"Example section relating to Rights",
    "license":"License for this dataset",
    'primary':json.dumps({
        'first_name':'Daniel',
        'last_name': 'Westwood',
        'orcid':'0009-0007-1866-5843',
        'email':"daniel.westwood@stfc.ac.uk"
    }),
    'funders': json.dumps([{
        'name': 'UKRI sect 2',
        'affiliation': 'University of York'
    }]),
    'institutions': json.dumps([{
        'name': 'University of York'
    }])

}
temp_token = '7f50f7e592902b23bef32e9a630d040e6e229685'
temp_token = '69cb69a038897da333211f193b564102586889ba'
#SITE_URL = 'https://cmip7-citations-main.rancher2.130.246.130.221.nip.io'
SITE_URL = 'http://localhost:8000'

print(
    requests.put(f'{SITE_URL}/api/citation/cmip7.aerchemmip.cccma.canesm6-mr.esm-scen7-h-aer_v1', 
        data=citation, 
        headers={'Authorization':f'Token {temp_token}'},
        verify=False
    ).content
)