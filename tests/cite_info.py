import requests

pay = {
    "data": {
        "type": "dois",
        "attributes": {
            "event": "publish",
            "creators": [
                {
                    "name": "Westwood, Daniel ",
                    "affiliation": [
                        {
                            "affiliationIdentifier": "https://ror.org/04m01e293",
                            "affiliationIdentifierScheme": "ROR",
                            "name": "University of York",
                            "schemeUri": "https://ror.org/",
                        },
                        {
                            "affiliationIdentifier": "https://ror.org/04j4kad11",
                            "affiliationIdentifierScheme": "ROR",
                            "name": "Centre for Environmental Data Analysis",
                            "schemeUri": "https://ror.org/",
                        },
                    ],
                }
            ],
            "titles": [
                {
                    "lang": "en",
                    "title": "ESGF-NG CMIP7 CMIP7.PMIP.MOHC.cnrm_esm2_1e.abrupt-127k",
                }
            ],
            "publisher": {
                "name": "STFC",
                "publisherIdentifier": "https://ror.org/057g20z61",
                "publisherIdentifierScheme": "ROR",
                "schemeUri": "https://ror.org/",
            },
            "publicationYear": 2026,
            "types": {"resourceTypeGeneral": "Text"},
            "url": "/citation/CMIP7.PMIP.MOHC.cnrm_esm2_1e.abrupt-127k_v1",
            "version": 1,
            "rightsList": [],
            "fundingReferences": [],
            "relatedIdentifiers": [
                {
                    "relatedIdentifier": "https://doi.org/10.1029/2019MS001683",
                    "relationType": "Cites",
                },
                {
                    "relatedIdentifier": "https://doi.org/10.1029/2019MS001791",
                    "relationType": "Cites",
                },
                {
                    "relatedIdentifier": "https://doi.org/10.22541/essoar.175977424.42948487/v1",
                    "relationType": "Cites",
                },
            ],
        },
    }
}

payload = {
    "data": {
        "type": "dois",
        "attributes": {
            "prefix":"10.83017",
            "creators": [
                {
                    "name": "Westwood, Daniel ",
                    "affiliation": [
                        {
                            "affiliationIdentifier": "https://ror.org/04m01e293",
                            "affiliationIdentifierScheme": "ROR",
                            "name": "University of York",
                            "schemeUri": "https://ror.org/",
                        },
                        {
                            "affiliationIdentifier": "https://ror.org/04j4kad11",
                            "affiliationIdentifierScheme": "ROR",
                            "name": "Centre for Environmental Data Analysis",
                            "schemeUri": "https://ror.org/",
                        },
                    ],
                }
            ],
            "titles": [
                {
                    "lang": "en",
                    "title": "Example Test 3",
                }
            ],
            "publisher": {
                "name": "STFC",
                "publisherIdentifier": "https://ror.org/057g20z61",
                "publisherIdentifierScheme": "ROR",
                "schemeUri": "https://ror.org/",
            },
            "publicationYear": 2026,
            "types": {"resourceTypeGeneral": "Text"},
            "url": "https://127.0.0.1:8000/citation/CMIP7.PMIP.MOHC.cnrm_esm2_1e.abrupt-127k_v2",
            "version": 2,
            "rightsList": [],
            "fundingReferences": [],
            "relatedIdentifiers": [
                {
                    "relatedIdentifier": "https://doi.org/10.1029/2019MS001683",
                    "relatedIdentifierType":"URL",
                    "relationType": "Cites",
                },
                {
                    "relatedIdentifier": "https://doi.org/10.1029/2019MS001791",
                    "relatedIdentifierType":"URL",
                    "relationType": "Cites",
                },
                {
                    "relatedIdentifier": "https://doi.org/10.22541/essoar.175977424.42948487/v1",
                    "relatedIdentifierType":"URL",
                    "relationType": "Cites",
                },
            ],
        },
    }
}

# r = requests.post(
#     'https://api.test.datacite.org/dois',
#     headers= {
#         "Content-Type": "application/vnd.api+json"},
#     data=example,
#     auth=("XFND.JKISEC","xopzyq-zozwa1-wYbmov")
#     )

# print(r, r.content)

url = "https://api.test.datacite.org/dois"

import base64

token = base64.b64encode(b"XFND.JKISEC:xopzyq-zozwa1-wYbmov").decode("utf-8")

headers = {
    "accept": "application/vnd.api+json",
    "content-type": "application/json",
    "authorization": f"Basic {token}",
}

response = requests.post(
    'https://api.test.datacite.org/dois',
    headers= {
        "Content-Type": "application/vnd.api+json"},
    json=payload,
    auth=("XFND.JKISEC","xopzyq-zozwa1-wYbmov")
    )

# response = requests.put(
#     'https://api.test.datacite.org/dois/10.83017/test-002',
#     headers= {
#         "Content-Type": "application/vnd.api+json"},
#     json=payload,
#     auth=("XFND.JKISEC","xopzyq-zozwa1-wYbmov")
#     )

#response = requests.post(url, json=payload, headers=headers)

print(response.text)
