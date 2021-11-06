import re

import string
from allauth.account.signals import user_signed_up
from django.contrib.auth.models import User
from django.db.models.signals import pre_save
from django.dispatch.dispatcher import receiver

from omegaops.tasks import deploy_user_service


@receiver(pre_save, sender=User)
def handle_username(sender, instance, **kwargs):
    user = instance
    # do not allow special characters in username
    if set(string.punctuation) & set(user.username):
        user.username = re.sub(f'[{string.punctuation}]', '', user.username)


@receiver(user_signed_up)
def handle_usersignup(sender, request=None, user=None, **kwargs):
    """
    handle user sign up
    """
    deploy_user_service(user.pk)
