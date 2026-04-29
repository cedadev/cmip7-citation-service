from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token


def test_create_token():
    usr = User.objects.get(username='abc123')
    token, created = Token.objects.get_or_create(user=usr)
    print('New token: ',token.key)

test_create_token()