import requests
import json

citation = {
    'title':'example_citation_yellow_8_blue_6',
    "abstract":"this is a test record, created by Daniel Westwood at CEDA",
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
        'name': 'UKRI sect 1',
        'affiliation': 'University of York'
    }]),
    'institutions': json.dumps([{
        'name': 'University of York'
    }])

}
temp_token = '69cb69a038897da333211f193b564102586889ba'

print(
    requests.post('http://localhost:8000/api/citations/', 
        data=citation, 
        headers={'Authorization':f'Token {temp_token}'}
    )
)