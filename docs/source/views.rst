============================
Citation Views and Rendering
============================

For a full listing of the available views, see the ``urls.py`` file.

Standard types of views available:
 - List views: Citations, Parties, Institutions, FundingStreams
 - Specific Record views: Citation, Party, Institution, FundingStreams
 - API List views: Citations, Parties, Institutions, FundingStreams
 - Specific API views: Citation, Party
 - Create/Edit UI view: Citation (able to create new instances of all the above)
 - Delete view: Citation (No other records able to be deleted via UI currently.)
 - Delete API views: Citations, Parties, Institutions, FundingStreams

Miscellaneous Other Views:
 - Reviewer Request: Allows users to request access to review records.

Render functions listed below may perform changes to the content rendered to the HTML view for a better user experience. This includes:
 - Adding links to the abstract paragraph based on references in the citation
 - Linking to the rights/licence info from the ``RIGHTS_MAP``
 - Rendering the references with linked DOIs and bold titles.
 - Rendering the Cite As option from the DOI and available info
 - Adding the STAC Code Snippet if available.

Permissions apply to all create/update/delete views including for the API (PUT/POST/DELETE methods), where a user/token provided must have both the ``add_citations`` and ``edit_<institution>`` permissions to edit an existing record, or just the ``add_citations`` permission to create new records.

.. automodule:: citations.views
    :members: