# Publication Workflow to Datacite for DOI Provisioning

## API Endpoint

DataCite endpoint: https://api.test.datacite.org/dois

## JSON Payload

- May want to add a CMIP7-specific suffix? I.e `ESGF/CMIP7.<5char>`

```
{
    "data": {
        "type":"dois",
        "attributes":{
            "event" : "publish", # For live publication
            "creators":[
                {
                    "name" "<last_name>, <first name> <middle names>",
                    "affiliation": [
                        {
                            "affiliationIdentifier": "<ror link>",
                            "affiliationIdentifierScheme":"ROR",
                            "name": "<name from institution model>",
                            "schemeUri": "https://ror.org/"
                        }
                    ],
                    "nameIdentifiers": [
                        {
                            "schemeUri": "https://orcid.org",
                            "nameIdentifier": "https://orcid.org/<orcid>",
                            "nameIdentifierScheme": "ORCID"
                        }
                    ]
                }
            ],
            "contributors": [
                {
                    "same as creators, but with contributorType as contact?"
                }
            ]
            "titles":[
                {
                    "lang": "en",
                    "title": "Citation Record for <citation.title>"
                }
            ],
            "publisher": "DataCite e.V.", # Or CEDA?
            "publicationYear": "", # Do we want this as a field in the citation service?
            "types": {
                "resourceTypeGeneral": "Text"
            },
            "url": "<citation-service-url>",
            "version": 1,
            "rightsList": [
                {
                    "rights info if can be related"
                }
            ],
            "fundingReferences": [
                {
                    "awardUri": "Additional data needed?"
                }
            ]
        }
    }
}
```

All possible attributes to fill are below

```
{
      "identifiers": [],
      "alternateIdentifiers": [],
      "creators": [
        {
          "name": "DataCite Metadata Working Group",
          "affiliation": [],
          "nameIdentifiers": []
        }
      ],
      "titles": [
        {
          "title": "DataCite Metadata Schema Documentation for the Publication and Citation of Research Data v4.0"
        }
      ],
      "publisher": "DataCite e.V.",
      "container": {},
      "publicationYear": 2016,
      "subjects": [],
      "contributors": [],
      "dates": [],
      "language": null,
      "types": {
        "schemaOrg": "ScholarlyArticle",
        "citeproc": "article-journal",
        "bibtex": "article",
        "ris": "RPRT",
        "resourceTypeGeneral": "Text"
      },
      "relatedIdentifiers": [],
      "relatedItems": [],
      "sizes": [],
      "formats": [],
      "version": null,
      "rightsList": [],
      "descriptions": [],
      "geoLocations": [],
      "fundingReferences": [],
      "xml": "PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiPz4KPHJlc291cmNlIHhtbG5zOnhzaT0iaHR0cDovL3d3dy53My5vcmcvMjAwMS9YTUxTY2hlbWEtaW5zdGFuY2UiIHhtbG5zPSJodHRwOi8vZGF0YWNpdGUub3JnL3NjaGVtYS9rZXJuZWwtNCIgeHNpOnNjaGVtYUxvY2F0aW9uPSJodHRwOi8vZGF0YWNpdGUub3JnL3NjaGVtYS9rZXJuZWwtNCBodHRwOi8vc2NoZW1hLmRhdGFjaXRlLm9yZy9tZXRhL2tlcm5lbC00L21ldGFkYXRhLnhzZCI+CiAgPGlkZW50aWZpZXIgaWRlbnRpZmllclR5cGU9IkRPSSI+MTAuNTQzOC9RNUU4LTk1ODU8L2lkZW50aWZpZXI+CiAgPGNyZWF0b3JzPgogICAgPGNyZWF0b3I+CiAgICAgIDxjcmVhdG9yTmFtZT5EYXRhQ2l0ZSBNZXRhZGF0YSBXb3JraW5nIEdyb3VwPC9jcmVhdG9yTmFtZT4KICAgIDwvY3JlYXRvcj4KICA8L2NyZWF0b3JzPgogIDx0aXRsZXM+CiAgICA8dGl0bGU+RGF0YUNpdGUgTWV0YWRhdGEgU2NoZW1hIERvY3VtZW50YXRpb24gZm9yIHRoZSBQdWJsaWNhdGlvbiBhbmQgQ2l0YXRpb24gb2YgUmVzZWFyY2ggRGF0YSB2NC4wPC90aXRsZT4KICA8L3RpdGxlcz4KICA8cHVibGlzaGVyPkRhdGFDaXRlIGUuVi48L3B1Ymxpc2hlcj4KICA8cHVibGljYXRpb25ZZWFyPjIwMTY8L3B1YmxpY2F0aW9uWWVhcj4KICA8cmVzb3VyY2VUeXBlIHJlc291cmNlVHlwZUdlbmVyYWw9IlRleHQiLz4KICA8c2l6ZXMvPgogIDxmb3JtYXRzLz4KICA8dmVyc2lvbi8+CjwvcmVzb3VyY2U+",
      "url": "https://example.org",
      "contentUrl": null,
      "metadataVersion": 0,
      "schemaVersion": null,
      "source": "api",
      "isActive": true,
      "state": "findable",
      "reason": null,
      "landingPage": null,
      "viewCount": 0,
      "viewsOverTime": [],
      "downloadCount": 0,
      "downloadsOverTime": [],
      "referenceCount": 0,
      "citationCount": 0,
      "citationsOverTime": [],
      "partCount": 0,
      "partOfCount": 0,
      "versionCount": 0,
      "versionOfCount": 0,
      "created": "2023-08-21T19:02:56.000Z",
      "registered": "2023-08-21T19:02:56.000Z",
      "published": "2016",
      "updated": "2023-08-21T19:02:56.000Z"
    }
```