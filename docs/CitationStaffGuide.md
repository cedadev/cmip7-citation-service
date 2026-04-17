# Guide to Citation Service Support for ESGF/CEDA Staff

## User Requesting Reviewer Permissions

Users may log in with their Github accounts to the Citation Service. This serves as a third party authentication for specific user accounts, and does not provide any additional privileges initially.

Logged in users can request reviewer permissions for one or more institution's citation records. This is via a button on the citation view for each record, and users may request any number of institution permissions. This triggers a message to the `citation-reviewer-requests` channel on ESGF slack, which notes the username and required institution-based permissions.

## Granting Permissions

Log into the citation service admin page (`/admin`) as the `esgfpub` user.

Navigate to `Authentication and Authorization` >> `Users` and locate the specific username being requested. Scroll down to `User permissions` and search for the required permissions.
- All reviewers MUST have the `Can add citations` permission.
- Institution-based permissions can be found just by searching the name of the institution.

Once user permissions have been chosen, click Save at the bottom. This will automatically post a message to the slack channel to let everyone know what permissions have been granted for this user.