# API/Form Updating expectations

## Create a new Party
    - ORCID used to fetch affiliations:
        - Connect ORCID affiliations to existing institutions in the database OR
        - Used in a call to ROR to collect information and register the institution
    - Affiliations provided manually (title of the Institution):
        - Connected to existing institutions in the database OR
        - Used in a call to ROR to collect information and register the institution

## Create an Institution (manually)
- Ability to add institutions
    - Upon creating an institution, information is pulled from ROR to determine and validate country of origin

## Create a Funding Stream
- Ability to add funding streams
    - Provided affiliation used to fetch institutions (as above)
        - Connected to existing institutions in the database OR
        - Used in a call to ROR to collect information and register the institution

## Create a Citation
- Citation title and 'version' number used to generate ID. Version auto-increments whenever a new entry with the same title is created. (NOTE: Updates to citations that do not include the version number should default to the latest version)
- All citations start as 'unpublished'
- Citations may start with no authors of any kind, but cannot be published in this state.

## Update a Citation
- Citation updates that include authors in the correct categories will be matched by first/last name. If multiple authors exist for the same first/last name combination, a middle name entry will be required. (NOTE: On adding a new Party, if the first/last name combination is not unique, a middle name entry will also be required.)
- Citation updates that include references will append to the existing set of references.
- Citation updates that include funding streams will be matched by stream name, which is the primary key for the funding stream database.

# Publication/DOI Service

- Will need manual input to proceed with DOI registration, need to explore how this can be done.