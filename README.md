# cmip7-citation-service

## Citations Table
name: string (300 char limit)
Abstract: string (unlimited?)
subjects: 
rights: string (license)
license: string (paragraph)
primary: -> <author>
Primary institute: -> <institution>
contacts: -> <authors>
funders: -> <funders>
cite as: string (300 char limit)
data access: (list)
Authors Table
Author ID (internal)
firstname: string
lastname: string
PID: orcid
affiliation -> institution

## Funders Table
Funding ID (internal)
name: Funding name
Affiliation -> institution

## Institution Table
name: Institute
IID: Institute ID
<Other Institution Metadata>

Relations - Unsure what these mean or how they are represented

## Web Interface
### Reading Data
REST API for json representations of objects from any table.
Display URLs for each table to display single records
Search interface?
### Writing Data
Use of CEDA or Internal login for updating content with Web Interface?
API-based updates with API-Key to specific url for creating new objects?
For a new citation entry:
Create any new institutions not present yet?
Add authors/funders as needed?
Create citation entry (can we create this first with blank entries?)
