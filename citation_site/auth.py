from mozilla_django_oidc.auth import OIDCAuthenticationBackend \
    as BaseOIDCAuthenticationBackend

class UsernameOIDCAuthenticationBackend(BaseOIDCAuthenticationBackend):
    """ Extends the mozilla-django-oidc OIDC authentication backend to handle 
    a user identified solely by a username, using the "preferred_username" value
    from an OIDC token. Also adds and updates their given and family name, and
    their email address if these are present in the token.
    """

    def get_username(self, claims):

        return claims.get("preferred_username")

    def describe_user_by_claims(self, claims):

        username = self.get_username(claims)
        return "username {}".format(username)

    def filter_users_by_claims(self, claims):

        """Return all users matching the specified username."""
        username = self.get_username(claims)
        if not username:
            return self.UserModel.objects.none()
        return self.UserModel.objects.filter(username__iexact=username)

    def verify_claims(self, claims):
        """Verify the provided claims to decide if authentication should be allowed."""

        # Verify claims required by default configuration
        scopes = self.get_settings("OIDC_RP_SCOPES", "openid email")
        if "openid" in scopes.split():
            return "preferred_username" in claims

        print('Custom OIDC_RP_SCOPES defined. '
                       'You need to override `verify_claims` for custom claims verification.')

        return True

    def create_user(self, claims):

        user = super().create_user(claims)

        user.first_name = claims.get("given_name", "")
        user.last_name = claims.get("family_name", "")
        user.save()

        return user

    def update_user(self, user, claims):

        user.email = claims.get("email", "")
        user.first_name = claims.get("given_name", "")
        user.last_name = claims.get("family_name", "")
        user.save()

        return user