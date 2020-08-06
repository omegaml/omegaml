from allauth.account.signals import user_signed_up
from django.contrib.auth.models import User
from django.core.management import BaseCommand

import omegaops


class Command(BaseCommand):
    help = 'Setup a user'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, help='username')
        parser.add_argument('--password', type=str, help='password')
        parser.add_argument('--email', type=str, help='email')
        parser.add_argument('--staff', action='store_true', help='is staff flag', default=False)
        parser.add_argument('--admin', action='store_true', help='is admin flag', default=False)
        parser.add_argument('--apikey', type=str, help='apikey')
        parser.add_argument('--verbose', action='store_true', help='verbose', default=False)
        parser.add_argument('--nodeploy', action='store_true', help='verbose', default=False)

    def handle(self, *args, **options):
        username = options['username']
        email = options.get('email') or '{}@omegaml.io'.format(username)
        assert username, 'You must specify a username'
        dbpassword = User.objects.make_random_password(length=36)
        # create/update django user
        try:
            user = User.objects.get(username=username)
        except:
            user_password = options.get('password') or User.objects.make_random_password(length=36)
            user = User.objects.create_user(username, email=email, password=user_password)
            user_signed_up.send(self, user=user)
            print('Password set', user_password)
        else:
            print("Warning: User exists already. Staff and apikey will be reset if specified.")
        # update staff and apikey
        user.is_superuser = options.get('admin') or False
        user.is_staff = user.is_superuser or options.get('staff') or False
        user.api_key.key = options.get('apikey') or user.api_key.key
        user.api_key.save()
        user.save()
        print("User {} created as superuser: {} staff: {}".format(user.username, user.is_superuser, user.is_staff))
        # add/update omega user
        if options.get('nodeploy') is False:
            config = omegaops.add_user(user, dbpassword, deploy_vhost=True)
            omegaops.add_service_deployment(user, config)
            print("Database {} deployed. Apikey {}. Is staff {}".format(user, user.api_key.key, user.is_staff))
            if options.get('verbose'):
                print("Config", config)
        else:
            print("No database deployed due to --nodeploy. Re-run without --nodeploy to create a database")
