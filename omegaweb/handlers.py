from allauth.account.signals import user_signed_up
from django.dispatch.dispatcher import receiver

from omegaops.tasks import deploy_user_service


@receiver(user_signed_up)
def handle_usersignup(sender, request=None, user=None, **kwargs):
    """
    handle user sign up
    """
    deploy_user_service(user.pk)