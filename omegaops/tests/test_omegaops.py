import pymongo
from uuid import uuid4

import datetime
import hashlib
from urllib.parse import urlparse

from constance import config as constance_config
from django.conf import settings
from django.contrib.auth.models import User, Group
from django.test.testcases import TestCase
from kombu import Connection
from pymongo.errors import PyMongoError, OperationFailure

from landingpage.models import ServicePlan
from omegaml.mongoshim import MongoClient
from omegaops import add_service_deployment, add_userdb, authorize_userdb, add_user, authorize_user_vhost, \
    get_client_config
from omegaml.util import settings as omsettings


class OmegaOpsTests(TestCase):
    def setUp(self):
        TestCase.setUp(self)
        # first user
        self.username = username = 'testuser@omegaml.io'
        self.email = email = 'testuser@omegaml.io'
        self.password = password = 'password'
        self.user = User.objects.create_user(username, email, password)
        # second user
        self.username2 = username2 = 'testuser2@omegaml.io'
        self.email2 = email2 = 'testuser2@omegaml.io'
        self.password2 = password2 = 'password2'
        self.user2 = User.objects.create_user(username2, email2, password2)
        # ops user
        self.opsusername = opsusername = 'omops'
        self.opsemail = opsemail = 'opsuser_test@omegaml.io'
        self.opspassword = opspassword = 'opsuser_test'
        self.user2 = User.objects.create_user(opsusername, opsemail, opspassword)

    def tearDown(self):
        TestCase.tearDown(self)

    def test_adduserdb(self):
        """
        test new users and mongo databases can be added with authentication
        """
        dbname = uuid4().hex
        username = uuid4().hex
        password = 'foobar'
        db, url = add_userdb(dbname, username, password)
        self.assertIsNotNone(db)
        # check we can use the db to insert data
        coll = db['data']
        coll.insert_one({'foo': 'bar'})
        # check a new user for another db cannot access old db
        dbname2 = uuid4().hex
        username2 = uuid4().hex
        password2 = 'foobar2'
        db2, url = add_userdb(dbname2, username2, password2)
        # check a valid user cannot get access to another db
        otherdb = db2.client[dbname]
        with self.assertRaises(OperationFailure) as ex:
            otherdb.list_collection_names()

    def test_addservice(self):
        """
        test adding a new service deployment works
        """
        # our new user should not have a plan deployment yet
        ServicePlan.objects.create(name='omegaml')
        self.assertIsNone(self.user.services.first())
        # create a new plan and plan deployment
        config = {
            'foo': 'bar',
        }
        add_service_deployment(self.user, config)
        # check it was actually added properly
        service = self.user.services.first()
        self.assertIsNotNone(service)
        plan = service.offering.name
        self.assertEqual(plan, 'omegaml')
        service_config = service.settings
        self.assertDictEqual(service_config, config)

    def test_adduser_authorize_userdb(self):
        """
        test users can authorize each other (database)
        """
        # setup service deployments
        ServicePlan.objects.create(name='omegaml')
        # create first user
        username = hashlib.md5(self.username.encode('utf-8')).hexdigest()
        password = hashlib.md5(self.password.encode('utf-8')).hexdigest()
        config = add_user(username, password)
        add_service_deployment(self.user, config)
        # check we can authenticate and insert
        mongo_url = settings.BASE_MONGO_URL.format(mongohost=constance_config.MONGO_HOST,
                                                   **config['qualifiers']['default'])
        client = MongoClient(mongo_url, authSource='admin')
        db = client.get_database()
        coll = db['data']
        coll.drop()
        coll.insert_one({'foo': 'bar-user1'})
        # add a second user
        username2 = hashlib.md5(self.username2.encode('utf-8')).hexdigest()
        password2 = hashlib.md5(self.password2.encode('utf-8')).hexdigest()
        config2 = add_user(username2, password2)
        add_service_deployment(self.user2, config2)
        mongo_url = settings.BASE_MONGO_URL.format(mongohost=constance_config.MONGO_HOST,
                                                   **config['qualifiers']['default'])
        client2 = MongoClient(mongo_url, authSource='admin')
        db2 = client2.get_database()
        coll2 = db2['data']
        coll2.insert_one({'foo': 'bar-user2'})
        # verify that second user does not have access to first user's db
        config_fail = dict(config2['qualifiers']['default'])
        config_fail['mongodbname'] = config['qualifiers']['default']['mongodbname']
        mongo_url = settings.BASE_MONGO_URL.format(mongohost=constance_config.MONGO_HOST,
                                                   **config_fail)
        client_fail = MongoClient(mongo_url, authSource='admin')
        with self.assertRaises(pymongo.errors.OperationFailure):
            db_fail = client_fail.get_database()
            coll_fail = db_fail['data']
            data = coll_fail.find_one()
        # authorize second user to first user's db
        config3 = authorize_userdb(self.user, self.user2, username2, password2)
        # see if we can access first user's db using second user's credentials
        qualified_config = config3.get(self.user.username)
        username3 = qualified_config.get('mongouser')
        password3 = qualified_config.get('mongopassword')
        dbname3 = qualified_config.get('mongodbname')
        mongo_url = settings.BASE_MONGO_URL.format(mongohost=constance_config.MONGO_HOST,
                                                   **config['qualifiers']['default'])
        client3 = MongoClient(mongo_url, authSource='admin')
        db3 = client3.get_database()
        coll3 = db3['data']
        data = coll3.find_one()
        self.assertEqual(data['foo'], 'bar-user1')
        coll3.insert_one({'foobar': 'bar-user2'})
        data = coll.find_one({'foobar': 'bar-user2'})
        self.assertEqual(data['foobar'], 'bar-user2')

    def test_adduser_authorize_user_vhost(self):
        """
        test users can authorize each other (broker)
        """
        # setup service deployments
        ServicePlan.objects.create(name='omegaml')
        # create first user
        username = hashlib.md5(self.username.encode('utf-8')).hexdigest()
        password = hashlib.md5(self.password.encode('utf-8')).hexdigest()
        config = add_user(username, password, deploy_vhost=True)
        add_service_deployment(self.user, config)
        # add a second user
        username2 = hashlib.md5(self.username2.encode('utf-8')).hexdigest()
        password2 = hashlib.md5(self.password2.encode('utf-8')).hexdigest()
        config2 = add_user(username2, password2, deploy_vhost=True)
        add_service_deployment(self.user2, config2)
        # authorize second user to first user's vhost
        brokeruser = config2['qualifiers']['default']['brokeruser']
        config3 = authorize_user_vhost(self.user, self.user2, brokeruser, password2)
        # see if we can access first user's vhost using second user's credentials
        qualified_config = config3.get(self.user.username)
        username3 = qualified_config.get('brokeruser')
        password3 = qualified_config.get('brokerpassword')
        dbname3 = qualified_config.get('brokervhost')
        config4 = get_client_config(self.user2, qualifier=self.user.username)
        broker_url = config4['OMEGA_CELERY_CONFIG']['BROKER_URL']
        use_ssl = config4['OMEGA_CELERY_CONFIG']['BROKER_USE_SSL']
        self.assertIsNone(self._test_broker(broker_url, use_ssl))

    def _test_broker(self, broker_url, use_ssl):
        with Connection(broker_url, ssl=use_ssl) as conn:
            conn.connect()
            simple_queue = conn.SimpleQueue('simple_queue')
            message_sent = 'helloworld, sent at {0}'.format(datetime.datetime.today())
            simple_queue.put(message_sent)
            simple_queue.close()
        with Connection(broker_url, ssl=use_ssl) as conn:
            simple_queue = conn.SimpleQueue('simple_queue')
            message_received = simple_queue.get(block=True, timeout=1)
            self.assertEqual(message_received.payload, message_sent)
            message_received.ack()
            simple_queue.close()

    def test_parse_client_config_v3(self):
        from constance import config as site_config

        ServicePlan.objects.create(name='omegaml')
        config = {
            'version': 'v3',
            'services': {
                'notebook': {
                    'url': 'nb_url',
                }
            },
            'qualifiers': {
                # TODO simplify -- use a more generic user:password@service/selector format
                'default': {
                    'mongodbname': 'dbname',
                    'mongouser': 'dbuser',
                    'mongopassword': 'dbpass',
                }
            }
        }
        defaults = omsettings()
        add_service_deployment(self.user, config)
        config = get_client_config(self.user, qualifier='default')
        self.assertIn('OMEGA_CELERY_CONFIG', config)
        self.assertIn('BROKER_URL', config['OMEGA_CELERY_CONFIG'])
        self.assertEqual(config['OMEGA_CELERY_CONFIG']['BROKER_URL'], site_config.BROKER_URL)
        self.assertIn('OMEGA_MONGO_URL', config)
        parsed = urlparse(defaults.OMEGA_MONGO_URL)
        mongo_url = 'mongodb://dbuser:dbpass@{parsed.hostname}:{parsed.port}/dbname'.format(**locals())
        self.assertEqual(config['OMEGA_MONGO_URL'], mongo_url)
        # internal view
        config = get_client_config(self.user, qualifier='default', view=True)
        self.assertIn('OMEGA_CELERY_CONFIG', config)
        self.assertIn('BROKER_URL', config['OMEGA_CELERY_CONFIG'])
        self.assertEqual(config['OMEGA_CELERY_CONFIG']['BROKER_URL'], site_config.BROKER_URL,)
        self.assertIn('OMEGA_MONGO_URL', config)
        parsed = urlparse(defaults.OMEGA_MONGO_URL)
        mongo_url = 'mongodb://dbuser:dbpass@{parsed.hostname}:{parsed.port}/dbname'.format(**locals())
        self.assertEqual(mongo_url, config['OMEGA_MONGO_URL'])
        # make sure there are on lower case configs passed into defaults
        # -- this is to avoid merging server-side config is not mixed with client side defaults
        self.assertTrue(all(k.isupper() for k in config))

    def test_parse_client_config_v3_custom_qualifier(self):
        from constance import config as site_config

        ServicePlan.objects.create(name='omegaml')
        config = {
            'version': 'v3',
            'services': {
                'notebook': {
                    'url': 'nb_url',
                }
            },
            'qualifiers': {
                'default': {
                    'mongodbname': 'dbname',
                    'mongouser': 'dbuser',
                    'mongopassword': 'dbpass',
                },
                'foobar': {
                    'mongodbname': 'dbnameX',
                    'mongouser': 'dbuserX',
                    'mongopassword': 'dbpassX',
                }
            }
        }
        defaults = omsettings()
        add_service_deployment(self.user, config)
        config = get_client_config(self.user, qualifier='foobar')
        self.assertIn('OMEGA_CELERY_CONFIG', config)
        self.assertIn('BROKER_URL', config['OMEGA_CELERY_CONFIG'])
        self.assertEqual(config['OMEGA_CELERY_CONFIG']['BROKER_URL'], site_config.BROKER_URL)
        self.assertIn('OMEGA_MONGO_URL', config)
        parsed = urlparse(defaults.OMEGA_MONGO_URL)
        mongo_url = 'mongodb://dbuserX:dbpassX@{parsed.hostname}:{parsed.port}/dbnameX'.format(**locals())
        self.assertEqual(config['OMEGA_MONGO_URL'], mongo_url)
        # internal view
        config = get_client_config(self.user, qualifier='foobar', view=True)
        self.assertIn('OMEGA_CELERY_CONFIG', config)
        self.assertIn('BROKER_URL', config['OMEGA_CELERY_CONFIG'])
        self.assertEqual(config['OMEGA_CELERY_CONFIG']['BROKER_URL'], site_config.BROKER_URL,)
        self.assertIn('OMEGA_MONGO_URL', config)
        parsed = urlparse(defaults.OMEGA_MONGO_URL)
        mongo_url = 'mongodb://dbuserX:dbpassX@{parsed.hostname}:{parsed.port}/dbnameX'.format(**locals())
        self.assertEqual(mongo_url, config['OMEGA_MONGO_URL'])
        # make sure there are on lower case configs passed into defaults
        # -- this is to avoid merging server-side config is not mixed with client side defaults
        self.assertTrue(all(k.isupper() for k in config))

    def test_parse_client_config_v3_group_qualifier(self):
        from constance import config as site_config

        ServicePlan.objects.create(name='omegaml')
        config = {
            'version': 'v3',
            'services': {
                'notebook': {
                    'url': 'nb_url',
                }
            },
            'qualifiers': {
                'default': {
                    'mongodbname': 'dbname',
                    'mongouser': 'dbuser',
                    'mongopassword': 'dbpass',
                },
            }
        }
        group_config = {
            'version': 'v3',
            'services': {
                'notebook': {
                    'url': 'nb_url',
                }
            },
            'qualifiers': {
                'default': {
                    'mongodbname': 'dbnameX',
                    'mongouser': 'dbuserX',
                    'mongopassword': 'dbpassX',
                },
                'special': {
                    'mongodbname': 'dbnameY',
                    'mongouser': 'dbuserY',
                    'mongopassword': 'dbpassY',
                },
            }
        }
        defaults = omsettings()
        group_user = User.objects.create_user('Gfoobar', 'groupadmin@example.com', 'foobar')
        group = Group.objects.create(name='foobar')
        group_user.groups.add(group)
        add_service_deployment(self.user, config)
        add_service_deployment(group_user, group_config)
        # expect the user's default to be returned (not member of group)
        config = get_client_config(self.user, qualifier='foobar')
        parsed = urlparse(defaults.OMEGA_MONGO_URL)
        mongo_url = 'mongodb://dbuser:dbpass@{parsed.hostname}:{parsed.port}/dbname'.format(**locals())
        self.assertEqual(config['OMEGA_MONGO_URL'], mongo_url)
        # expect the group's default to be returned (user is member of group)
        self.user.groups.add(group)
        config = get_client_config(self.user, qualifier='foobar')
        parsed = urlparse(defaults.OMEGA_MONGO_URL)
        mongo_url = 'mongodb://dbuserX:dbpassX@{parsed.hostname}:{parsed.port}/dbnameX'.format(**locals())
        self.assertEqual(config['OMEGA_MONGO_URL'], mongo_url)
        # expect the group's special to be returned (user is member of group)
        config = get_client_config(self.user, qualifier='foobar:special')
        parsed = urlparse(defaults.OMEGA_MONGO_URL)
        mongo_url = 'mongodb://dbuserY:dbpassY@{parsed.hostname}:{parsed.port}/dbnameY'.format(**locals())
        self.assertEqual(config['OMEGA_MONGO_URL'], mongo_url)





