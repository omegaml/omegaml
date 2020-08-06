from django.contrib.auth.models import User
from django.core.management import BaseCommand

import omegaops


class Command(BaseCommand):
    help = "Authorize a user to an other user's database"

    def add_arguments(self, parser):
        parser.add_argument('--giver', type=str, help='giving username')
        parser.add_argument('--grantee', type=str, help='grantee username')

    def handle(self, *args, **options):
        giver_name = options['giver']
        grantee_name = options['grantee']
        assert giver_name and grantee_name, "Must provide --giver and --grantee"
        giver = User.objects.get(username=giver_name)
        grantee = User.objects.get(username=grantee_name)
        dbuser = User.objects.make_random_password(length=36)
        dbpassword = User.objects.make_random_password(length=36)
        omegaops.authorize_userdb(giver, grantee, dbuser, dbpassword)
        omegaops.authorize_user_vhost(giver, grantee, dbuser, dbpassword)
        print("User {grantee_name} granted access to qualifer={giver_name}".format(**locals()))
