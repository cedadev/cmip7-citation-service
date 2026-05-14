# cmip7-citation-service

CMIP7 is a project of the World Climate Research Programme (WCRP), coordinated by the Working Group on Coupled Modelling (WGCM).
Phase 7 builds on previous phases executed under the leadership of the Program for Climate Model Diagnosis and Intercomparison (PCMDI) and relies on the Earth System Grid Federation (ESGF) and the Centre for Environmental Data Analysis (CEDA) along with numerous related activities for implementation.

The CMIP7 Citation Service is hosted at https://cmip7-citations.ceda.ac.uk and allows the creation of citation records for ESGF-NG datasets (CMIP7, CORDEX-CMIP6) directly via the UI, using the service REST API or automatically as part of the ESGF-NG publication workflow.

NOTE: The ESGF-NG Publication Workflow Listener (KafkaListener) is not in production as of 14/05/2026 while the production Kafka systems are being assembled. Only the manual UI/API methods are available for creating records

## Information for Citation Record DOI Minting

It is possible to use the citation service to mint DOIs for records as needed. This requires an approving party to use either the UI or API to 'publish' the information via STFC's DataCite account for the Citation Service.
Use of the Citation Service, including reviewing citation records and approving for publication can be found in the Citation Reviewer Guide: https://github.com/cedadev/cmip7-citation-service/blob/main/docs/CitationReviewerGuide.pdf

NOTE: The DataCite publication workflow is not in production as of 14/05/2026, pending the formal agreement of DOI responsibilities with the Consortium leaders at STFC.