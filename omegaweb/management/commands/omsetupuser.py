import omegaops
from allauth.account.signals import user_signed_up
from django.contrib.auth.models import User
from django.core.management import BaseCommand


class Command(BaseCommand):
    help = 'Setup a user'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, help='username')
        parser.add_argument('--email', type=str, help='email')
        parser.add_argument('--staff', action='store_true', help='is staff flag')
        parser.add_argument('--apikey', type=str, help='apikey')
        parser.add_argument('--verbose', action='store_true', help='verbose')

    def handle(self, *args, **options):
        username = options['username']
        email = options.get('email') or '{}@omegaml.io'.format(username)
        assert username, 'You must specify a username'
        dbpassword = User.objects.make_random_password(length=36)
        # create/update django user
        try:
            user = User.objects.get(username=username)
        except:
            user_password = User.objects.make_random_password(length=36)
            user = User.objects.create_user(username, email=email, password=user_password)
            user_signed_up.send(self, user=user)
            print('Password set', user_password)
        else:
            print("Warning: User exists already. Staff and apikey will be reset if specified.")
        # update staff and apikey
        user.is_staff = options.get('staff')
        user.api_key.key = options.get('apikey') or user.api_key.key
        user.api_key.save()
        user.save()
        # add/update omega user
        config = omegaops.add_user(user, dbpassword)
        omegaops.add_service_deployment(user, config)
        print("User {} added. Apikey {}. Is staff {}".format(user, user.api_key.key, user.is_staff))
        if options.get('verbose'):
            print("Config", config)
