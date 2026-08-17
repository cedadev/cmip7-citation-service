Admins of the Citation Service
==============================

Special instructions for Citation service admins:

Approving Reviewer Permissions
------------------------------
- Check the ESGF slack workspace channel ``citation_reviewer_requests`` to see all pending citation reviewer requests. Requests that have been granted will have a corresponding message to state that a user has received permissions.
- Log into the admin page ``/admin``
- Go to Users and find the desired user (github username)
- Scroll down to the permissions section, find ``add citations`` plus any institution-based permission and click to move it to the granted permissions section on the left.
- Click save - this will automatically send a message to the slack channel, but the user will not be contacted as there may not be an email attached to their github account that is queryable.

Check failed requests
---------------------
If API-based POST requests are received, get past initial checks to form a title then are found to be invalid in validation checks, this will generate an entry in the ``/failed`` view that is visible only to admins. The entry recorded to then identify issues with the listener/service, fix issues and eventually retry the request with corrected details. Once the entry with corresponding title has been fixed, that entry will be removed from the ``/failed`` view on next loading.