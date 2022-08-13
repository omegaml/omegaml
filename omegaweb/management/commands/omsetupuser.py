from allauth.account.signals import user_signed_up
from django.contrib.auth.models import User
from django.core.management import BaseCommand

import omegaops
from landingpage.handlers import create_stripe_customer
from omegaops import create_omegaml_user

# we have esssential two ways to set up a new user
#
# 1. Using the setupuser command
# 2. Create a new user through the UI or REST API, or
#    the setupuser command with the --async flag set
#
# Using this command does the following (without the --async flag)
# 1. create the new user if it does not exist
# 2. reset any of the specified options (staff, apikey)
# 3. create a new 'omegaml' deployment if it does not exist
#
# Using the UI, REST API or the setupuser command with the --async flag
# 1. create the new user
# 2. assign an apikey
# 3. Issue install commands for services 'signup' and 'omegaml'
#    Use the runservices command to see the status.

class Command(BaseCommand):
    help = 'Setup a user'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, help='username')
        parser.add_argument('--password', type=str, help='password')
        parser.add_argument('--email', type=str, help='email')
        parser.add_argument('--staff', action='store_true', help='is staff flag', default=False)
        parser.add_argument('--admin', action='store_true', help='is admin flag', default=False)
        parser.add_argument('--apikey', type=str, help='apikey', default=None)
        parser.add_argument('--reveal', action='store_true', help='reveal user config and keys', default=False)
        parser.add_argument('--stripe', action='store_true', help='register user with stripe')
        parser.add_argument('--shovel', action='store_true', help='create vhost shovel')
        parser.add_argument('--verbose', action='store_true', help='verbose', default=False)
        parser.add_argument('--nodeploy', action='store_true', help='do not deploy the omegaml service for this user', default=False)
        parser.add_argument('--force', action='store_true', help='verbose', default=False)
        parser.add_argument('--async', action='store_true', help='create user async by omops', default=False)
        parser.add_argument('--vhost', action='store_true', help='create a rmq vhost for this user', default=False)

    def handle(self, *args, **options):
        username = options['username']
        email = options.get('email') or '{}@omegaml.io'.format(username)
        assert username, 'You must specify a username'
        is_superuser = options.get('admin') or False
        is_staff = is_superuser or options.get('staff') or False
        # create/update django user
        try:
            user = User.objects.get(username=username)
        except:
            user_password = options.get('password') or User.objects.make_random_password(length=36)
            user = User.objects._create_user(username, email=email, password=user_password,
                                             is_staff=is_staff, is_superuser=is_superuser)
            print('Password was reset', user_password if options.get('reveal') else '***')
            user.emailaddress_set.create(email=email, verified=True, primary=True)
            print('Email address verified', email)
            print("User {} created as superuser: {} staff: {}".format(user.username, user.is_superuser, user.is_staff))
            # note this only triggers the user_signed_up handler if requested
            # -- immediate deployment is done by create_omegaml_user call below
            # -- if async is specified, treat this the same way as if the user signed up by API or
            if options.get('async'):
                options['nodeploy'] = True
                user_signed_up.send(self, user=user)
        else:
            print("Warning: User exists already. Specify --apikey or --staff to reset, or --force to recreate the user.")
        # update apikey
        if options.get('apikey'):
            user.api_key.key = options.get('apikey')
            user.api_key.save()
            user.save()
            print(f"apikey has been set.")
        # change staff/admin setting
        if user.is_staff != options.get('staff'):
            user.is_staff = options.get('staff')
            user.save()
        print(f"User is superuser: {user.is_superuser} staff: {user.is_staff}")
        # add/update omega user if not exists or forced to recreate
        should_deploy = not options.get('nodeploy')
        should_deploy &= not options.get('async')
        should_deploy |= options.get('force')
        if should_deploy:
            if options.get('force') or not user.services.filter(offering__name='omegaml').exists():
                config = create_omegaml_user(user, deploy_vhost=options.get('vhost'))
                print("User services {} deployed. Is staff {}".format(user, user.is_staff))
                if options.get('verbose'):
                    print("Config", config)
            else:
                print("No database deployed due to deployment exists already. Specify --force to redeploy (may result in data loss!)")
        else:
            print("No database deployed due to --nodeploy or --async. Re-run without --nodeploy to create a database")
        if options.get('shovel'):
            omegaops.create_ops_forwarding_shovel(user)
        if options.get('stripe'):
            create_stripe_customer(user)
        if options.get('reveal'):
            deployment = user.services.filter(offering__name='omegaml').first()
            config = deployment.settings if deployment is not None else "not deployed"
            print(f'User: {user.username}')
            print(f'Email: {user.email}')
            print(f'Apikey: {user.api_key.key}')
            print(f'Config: {config}')
