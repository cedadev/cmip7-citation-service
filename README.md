# cmip7-citation-service

## Citations Table
name: string (300 char limit)
Abstract: string (unlimited?)
subjects: 
rights: string (license)
license: string (paragraph)
primary: -> <author> # ManyToOne or ManyToMany
Primary institute: -> <institution> # ManyToOne
contacts: -> <authors> # ManyToMany
funders: -> <funders> # ManyToMany
cite as: string (300 char limit)
data access: (list)

## Authors Table
Author ID (internal)
firstname: string
lastname: string
PID: orcid
affiliation -> institution # Many

## Funders Table
Funding ID (internal)
name: Funding name
Affiliation -> institution

## Institution Table
name: Institute
IID: Institute ID
<Other Institution Metadata>

## External References Table
Table for listing external DOI references that are not part of the CMIP7 citations model
title, year, authorset, doi

OR

reference text (full text?)

## Database table relations

Citation -> primary author # Many to One
Citation -> contacts # Many to Many
Citation -> primary institute # Many to One
Citation -> Funders # Many to Many

Author Affiliation -> Institute # Many to One
Funder Affiliation -> Institute # Many to One

## Web Interface
### Reading Data
REST API for json representations of objects from any table.
Display URLs for each table to display single records
Search interface?

#### URLs:
- API to all model views
- Main model views (display all/search page with no content)
- Specific model views (use ID or alternative for page viewing)

### Writing Data
Use of CEDA or Internal login for updating content with Web Interface?
API-based updates with API-Key to specific url for creating new objects?
For a new citation entry:
Create any new institutions not present yet?
Add authors/funders as needed?
Create citation entry (can we create this first with blank entries?)

# Token Authentication
