import re
import string
from allauth.account.signals import user_signed_up
from django.contrib.auth.models import User
from django.db.models.signals import pre_save
from django.dispatch.dispatcher import receiver

from landingpage.models import ServicePlan
from paasdeploy.models import ServiceDeployCommand
from omegaops import tasks  # noqa import to initialize omops celery


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
    # previously we run the task locally by calling
    #   deploy_user_service(user.pk)
    # now we just create a command and have omops execute it async
    # rationale:
    # - scalable as it does not block the user signup proces
    # - customizable as we can create any scripting for the command
    # issue command to add a new user
    plan = ServicePlan.objects.get(name='signup')
    ServiceDeployCommand.objects.create(offering=plan,
                                        user=user,
                                        phase='install')
    # -- issue command to deploy omegaml
    plan = ServicePlan.objects.get(name='omegaml')
    ServiceDeployCommand.objects.create(offering=plan,
                                        user=user,
                                        phase='install')
