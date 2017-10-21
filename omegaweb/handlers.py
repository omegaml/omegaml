
from allauth.account.signals import user_signed_up
from django.contrib.auth.models import User
from django.dispatch.dispatcher import receiver

from omegaops import add_user, add_service_deployment


@receiver(user_signed_up)
def handle_usersignup(sender, request=None, user=None, **kwargs):
    """
    handle user sign up
    """
    dbname = user.username
    username = User.objects.make_random_password(length=36)
    password = User.objects.make_random_password(length=36)
    add_user(dbname, username, password)
    config = {
        'dbname': dbname,
        'username': username,
        'password': password,
    }
    add_service_deployment(user, config)
