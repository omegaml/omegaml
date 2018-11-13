import hashlib

from allauth.account.signals import user_signed_up
from django.contrib.auth.models import User
from django.dispatch.dispatcher import receiver
from landingpage.models import DEPLOY_COMPLETED


@receiver(user_signed_up)
def handle_usersignup(sender, request=None, user=None, **kwargs):
    """
    handle user sign up
    """
