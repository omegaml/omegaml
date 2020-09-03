from allauth.account.signals import user_signed_up
from django.contrib.auth.models import User
from django.core.management import BaseCommand

import omegaops
from landingpage.handlers import create_stripe_customer


class Command(BaseCommand):
    help = 'Setup a user'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, help='username')
        parser.add_argument('--password', type=str, help='password')
        parser.add_argument('--email', type=str, help='email')
        parser.add_argument('--staff', action='store_true', help='is staff flag', default=False)
        parser.add_argument('--admin', action='store_true', help='is admin flag', default=False)
        parser.add_argument('--apikey', type=str, help='apikey', default=None)
        parser.add_argument('--stripe', action='store_true', help='register user with stripe')
        parser.add_argument('--verbose', action='store_true', help='verbose', default=False)
        parser.add_argument('--nodeploy', action='store_true', help='verbose', default=False)
        parser.add_argument('--force', action='store_true', help='verbose', default=False)

    def handle(self, *args, **options):
        username = options['username']
        email = options.get('email') or '{}@omegaml.io'.format(username)
        assert username, 'You must specify a username'
        dbpassword = User.objects.make_random_password(length=36)
        is_superuser = options.get('admin') or False
        is_staff = is_superuser or options.get('staff') or False
        # create/update django user
        try:
            user = User.objects.get(username=username)
        except:
            user_password = options.get('password') or User.objects.make_random_password(length=36)
            user = User.objects._create_user(username, email, user_password,
                                             is_staff, is_superuser)
            user_signed_up.send(self, user=user)
            print('Password set', user_password)
            user.emailaddress_set.create(email=email, verified=True, primary=True)
            print('Email address verified', email)
            print("User {} created as superuser: {} staff: {}".format(user.username, user.is_superuser, user.is_staff))
        else:
            print("Warning: User exists already. Staff and apikey will be reset if specified.")
        # update apikey
        if options.get('apikey'):
            user.api_key.key = options.get('apikey')
            user.api_key.save()
            user.save()
        print(f"apikey is {user.api_key.key}")
        # change staff/admin setting
        if user.is_staff != options.get('staff'):
            user.is_staff = options.get('staff')
            user.save()
        print(f"User is superuser: {user.is_superuser} staff: {user.is_staff}")
        # add/update omega user
        if options.get('nodeploy') is False:
            if options.get('force') or not user.services.filter(offering__name='omegaml').exists():
                config = omegaops.add_user(user, dbpassword, deploy_vhost=True)
                print("User services {} deployed. Apikey {}. Is staff {}".format(user, user.api_key.key, user.is_staff))
                if options.get('verbose'):
                    print("Config", config)
            else:
                print("No database deployed due to deployment exists already. Specify --force to redeploy (may result in data loss!)")
            omegaops.create_ops_forwarding_shovel(user)
        else:
            print("No database deployed due to --nodeploy. Re-run without --nodeploy to create a database")
        if options.get('stripe'):
            create_stripe_customer(user)
