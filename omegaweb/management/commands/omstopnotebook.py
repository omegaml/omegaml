

import omegaops
from django.contrib.auth.models import User
from django.core.management import BaseCommand


class Command(BaseCommand):
    help = 'Stop notebook server'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, help='username')

    def handle(self, *args, **options):
        username = options['username']
        omegaops.stop_usernotebook(username)
