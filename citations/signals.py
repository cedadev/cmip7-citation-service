from django.contrib.auth.models import User, Permission
from django.db.models.signals import m2m_changed
from django.dispatch import receiver

from django.conf import settings
from slack_sdk import WebClient

@receiver(m2m_changed, sender=User.user_permissions.through)
def user_permission_changed(sender, instance, action, pk_set, **kwargs):
    if action == "post_add":
        # Check if a specific permission was added
        target_perm = Permission.objects.get(codename="add_citations")

        if target_perm.pk in pk_set:
            # Run your custom operation
            response_text = f':white_check_mark: Github user: {instance.username} ({instance.first_name} {instance.last_name}) ' \
                'has been granted Reviewer access.'
            
            if settings.DEBUG:
                response_text += ' This is a test message'

            slack_client = WebClient(token=settings.SLACK_OAUTH_TOKEN)
            slack_client.chat_postMessage(
                channel=settings.SLACK_ESGF_CHANNEL,
                text=response_text,
                username='CEDA Citation SVC'
            )
