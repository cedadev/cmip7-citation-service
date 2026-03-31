# Description of Internal Citation Kafka Topic

- All kafka messages are timestamped so order is always preserved.
- Multiple submitters/listeners allowed, so all nodes can synchronise database (or other implementation) backends.
- Implementation on the backend does not matter between nodes. The only requirement is to use the following message format.

## Message format

### General message structure.

All messages must consist of `table`, `method` and `content` fields, where `table` refers to the database table structures created by the main node:
- citations
- parties
- institutions
- fundingstreams

Method refers to the write-required methods that services must perform via the Kafka queue:
- create
- update
- delete

Any method that does not require write access (i.e get/list) can be handled separately from the Kafka queue.

The content field is unique to each table, based on the properties of a record in that table. 

`delete` method: Only required property in the `content` field is the `id` of the record being deleted.
`update` method: Requires `id` and at least one other field, where that field is not `immutable` on the model (i.e is part of the ID construction)

### Record IDs

The IDs for each table are generated in such a way that they are:
- unique for each record being generated
- the same regardless of which node generates the `content` field.

IDs for each table follow the rules below:
- `citations`: `<title>_v<version>` where the title is comprised of the `mip_era`,`activity`,`institution`,`source` and `experiment` fields (joined by `.` dots) which match exactly the values in the EMD repository. The version is an integer incrementing value, where any node will increment this value if a record already exists with the same `title`. 
- `parties`: The party ID is the result of performing `hashlib.sha1(naming_hash.encode()).hexdigest()` where the `naming_hash` is the string values of `first_name`, `middle_names` and `last_name` properties of the record.
- `institutions`: The Institution ID is the result of performing `hashlib.sha1(naming_hash.encode()).hexdigest()` where the `naming_hash` is the accepted Title of the institution, according to the ROR (Research Organisation Registry).
- `fundingstreams`: The funding stream ID is the result of performing `hashlib.sha1(naming_hash.encode()).hexdigest()` where the `naming_hash` is the name of the funding stream. There is yet to be an agreed upon format for funding stream names, this should be discussed by the Citations team.

### Fields 

#### Quicklook required fields

`citations`
- title
- version - int
- id (comprised of the above two)
- published - bool
- editable - bool
- primary_id - ID of the party record with which to link this field (NOT party information)

`parties`
- first_name
- last_name
- id

`institutions`
- name
- id

`fundingstreams`
- name
- id

Note: All fields where no description is provided may be assumed to be string-based.

#### Citations Content Fields

Required fields of a citation `create` message:
- title
- version - int
- id (comprised of the above two)
- published - bool
- editable - bool
- primary_id - ID of the party record with which to link this field (NOT party information)

The below fields should also be provided at the point of creation but their absence may not be treated as not allowed.
- mip_era
- activity_id
- institution_id
- source_id
- experiment_id

Other fields of a citation `create` message are below. Any fields not included in the message should be saved as empty/blank for this record. Updates may later add further information to this record.
- abstract
- drs_url
- doi_url
- rights
- license
- contacts - List of IDs of the party records to attach as contacts (NOT party information)
- institutions - List of institution IDs
- funders - List of funder IDs

Note that the above message contains ALL information to create the low-level record. No further determination of information is necessary, from the above list of information.

#### Parties Content Fields

Required fields for a party `create` message:
- first_name
- last_name
- id (comprised of the above two and middle_names if provided)

Optional fields to include
- middle_names
- email
- orcid
- affiliations - List of IDs to `institutions` records.

#### Institutions Content Fields

Required for `create` messages:
- name
- id

Optional fields to include:
- acronym
- country

#### Fundingstreams Content Fields

Required for `create` messages:
- name
- id

Optional fields to include:
- affiliation_id - ID of `institutions` record to which this record is affiliated.