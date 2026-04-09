import requests
import json

citation = {
    'title':'cmip7.aerchemmip.cccma.cnrm_esm2_1e.esm-scen7-h-aob',
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
    'contacts':json.dumps([{
        'first_name':'David',
        'last_name': 'Westwood',
        'orcid':'0009-0007-1866-5843',
        'email':"daniel.westwood@stfc.ac.uk"
    },{
        'first_name':'Jesse',
        'last_name': 'Alexander',
        'orcid':'0009-0006-2877-3197',
    }]),
    'funders': json.dumps([{
        'name': 'UKRI sect 3',
        'affiliation': 'York University'
    }]),
    'institutions': json.dumps([{
        'name': 'York University'
    }]),
    'cites':json.dumps([{
        'title':'A very long way to a small angry title, with additional bits and a lengthy description (2026)',
        'citeas':"A very long way to a small angry title, with additional bits and a lengthy description (2026). Westwood, D.; Alexander, J.; Sykes, E. doi.org/1j2rthf", 'id':'doi.org/1j2rthf'
    }])

}
temp_token = '7f50f7e592902b23bef32e9a630d040e6e229685'
temp_token = '69cb69a038897da333211f193b564102586889ba'
#SITE_URL = 'https://cmip7-citations-main.rancher2.130.246.130.221.nip.io'
SITE_URL = 'http://localhost:8000'

print(
    requests.post(f'{SITE_URL}/api/citations/', 
        data=citation, 
        headers={'Authorization':f'Token {temp_token}'},
        verify=False
    ).content
)