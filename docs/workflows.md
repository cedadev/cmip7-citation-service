# CEDA Citation/Aggregation Workflows

## Citation Service

- Listener sidecar/side service listens to ESGF Kafka publisher topic - sends a facets-only message to the citation service.
- Citation service only creates a new version if the old version is not editable!!
    - Citation front sends write request as necessary (if any updates are needed)
    - On create, trigger ESGF update mechanism.
    - Citation back makes changes to the DB
- On publication
    - Minting service used to create DOI
    - Citation record private details are adjusted (editable, published)

## Aggregation

### CREPP Pipeline

Outputs test files to:
```
/home/users/esgfpub/manifests/test/cmip7/
```

and production files to:
```
/home/users/esgfpub/manifests/prod/cmip7/
```

### SHEPARD

- Runs sweep to collect all files from CREPP manifests and puts them in `/gws/ssde/j25b/cedaproc/shepard/cmip7/inputs`
- Runs project grouping and creates additional files in `/gws/ssde/j25b/cedaproc/shepard/cmip7/group_files`
- Initialises groups (up to some limit allowed in the pipeline at any one time (i.e 100))
- Run all pipeline deployment steps
- Run parallel completion (need a standby message for this)
- Run ingestion callable for any project where the complete status is Success
- Run deletion for any groups where the whole group is complete Success.

### Ingestion callable
- Ingest files to correct locations in the CEDA archive
- Push file references to STAC or via `esgadd` tool.


Required for accessing cron jobs via `esgfpub` user:
```
sudo -u esgfpub bash
```