import omegaops
from allauth.account.signals import user_signed_up
from django.contrib.auth.models import User
from django.core.management import BaseCommand


class Command(BaseCommand):
    help = 'Setup a user'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, help='username')
        parser.add_argument('--email', type=str, help='email')
        parser.add_argument('--staff', type=bool, help='is staff flag')

    def handle(self, *args, **options):
        username = options['username']
        dbpassword = User.objects.make_random_password(length=36)
        # create/update django user
        try:
            user = User.objects.get(username=username)
        except:
            email = options.get('email') or '{}@omegaml.io'.format(username)
            user_password = User.objects.make_random_password(length=36)
            user = User.objects.create_user(username, email=email, password=user_password)
            user_signed_up.send(self, user=user)
            print('Password set', user_password)
        if options.get('staff'):
            user.is_staff = True
            user.save()
        # add/update omega user
        config = omegaops.add_user(user, dbpassword)
        omegaops.add_service_deployment(user, config)
        print("User {} added. Apikey {}".format(user, user.api_key.key))
