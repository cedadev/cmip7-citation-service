from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from rest_framework.authtoken.models import Token


class Command(BaseCommand):
    help = "Runs backend listener"

    def add_arguments(self, parser):
        parser.add_argument("username", type=str, help="Username")
        parser.add_argument(
            "-f", "--force_create", dest="force_create", action="store_true"
        )

    def handle(self, username: str, force_create: bool = False, **kwargs):
        token(username, force_create=force_create)


def token(username: str, force_create: bool):

    if not User.objects.filter(username=username):
        u = User.objects.create(username=username)
        u.save()

    user = User.objects.get(username=username)

    if force_create:
        Token.objects.filter(user=user).delete()
    token, created = Token.objects.get_or_create(user=user)

    print(token)
