===================
DOI Minting Service
===================

A DOI is minted via a request to the DataCite API with the relevant info. This is attempted if the UI checkbox ``Publish on Save`` is clicked before saving the record, or if the value ``publish_on_save`` is set as ``true`` in an API POST/PUT request made to the citation service.

.. automodule:: citations.external.minting
    :members: