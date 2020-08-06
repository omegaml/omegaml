import datetime
import hashlib
from urllib.parse import urlparse

from constance import config as constance_config
from django.conf import settings
from django.contrib.auth.models import User
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

    def tearDown(self):
        TestCase.tearDown(self)

    def test_adduserdb(self):
        """
        test new users and mongo databases can be added with authentication
        """
        dbname = 'testdbops'
        username = 'testuserops'
        password = 'foobar'
        db, url = add_userdb(dbname, username, password)
        self.assertIsNotNone(db)
        # check we can authenticate and insert
        db.logout()
        db.authenticate(username, password, source='admin')
        coll = db['data']
        coll.insert({'foo': 'bar'})
        # check no other user can authenticate
        with self.assertRaises(PyMongoError) as ex:
            db.logout()
            db.authenticate('sillyuser', 'norealpassword', source='admin')
        # check a new user for another db cannot access old db
        dbname2 = 'testdbops2'
        username2 = 'testuserops2'
        password2 = 'foobar2'
        db2, url = add_userdb(dbname2, username2, password2)
        with self.assertRaises(PyMongoError) as ex:
            db.logout()
            db.authenticate(username2, password2, source='admin')
            db.create_collection('test')
        # check a valid user cannot get access to another db
        db2.logout()
        db2.authenticate(username2, password2, source='admin')
        otherdb = db2.client[dbname]
        with self.assertRaises(OperationFailure) as ex:
            otherdb.collection_names()

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
        coll.remove()
        coll.insert({'foo': 'bar-user1'})
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
        coll2.insert({'foo': 'bar-user2'})
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
        coll3.insert({'foobar': 'bar-user2'})
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

    def test_parse_client_config_v1(self):
        ServicePlan.objects.create(name='omegaml')
        config = {
            'default': {
                'dbname': 'dbname',
                'user': 'dbuser',
                'password': 'dbpass',
                'notebook_url': 'nb_url',
            }
        }
        defaults = omsettings()
        add_service_deployment(self.user, config)
        config = get_client_config(self.user, qualifier='default')
        self.assertIn('OMEGA_CELERY_CONFIG', config)
        self.assertIn('BROKER_URL', config['OMEGA_CELERY_CONFIG'])
        self.assertEqual(defaults.OMEGA_BROKER, config['OMEGA_CELERY_CONFIG']['BROKER_URL'])
        self.assertIn('OMEGA_MONGO_URL', config)
        parsed = urlparse(defaults.OMEGA_MONGO_URL)
        mongo_url = 'mongodb://dbuser:dbpass@{parsed.hostname}:{parsed.port}/dbname'.format(**locals())
        self.assertEqual(mongo_url, config['OMEGA_MONGO_URL'])
        # internal view
        config = get_client_config(self.user, qualifier='default', view=True)
        self.assertIn('OMEGA_CELERY_CONFIG', config)
        self.assertIn('BROKER_URL', config['OMEGA_CELERY_CONFIG'])
        self.assertEqual(defaults.OMEGA_BROKER, config['OMEGA_CELERY_CONFIG']['BROKER_URL'])
        self.assertIn('OMEGA_MONGO_URL', config)
        parsed = urlparse(defaults.OMEGA_MONGO_URL)
        mongo_url = 'mongodb://dbuser:dbpass@{parsed.hostname}:{parsed.port}/dbname'.format(**locals())
        self.assertEqual(mongo_url, config['OMEGA_MONGO_URL'])

    def test_parse_client_config_v2(self):
        ServicePlan.objects.create(name='omegaml')
        config = {
            'version': 'v2',
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
                }
            }
        }
        defaults = omsettings()
        add_service_deployment(self.user, config)
        # external view
        config = get_client_config(self.user, qualifier='default')
        self.assertIn('OMEGA_CELERY_CONFIG', config)
        self.assertIn('BROKER_URL', config['OMEGA_CELERY_CONFIG'])
        self.assertEqual(defaults.OMEGA_BROKER, config['OMEGA_CELERY_CONFIG']['BROKER_URL'])
        self.assertIn('OMEGA_MONGO_URL', config)
        parsed = urlparse(defaults.OMEGA_MONGO_URL)
        mongo_url = 'mongodb://dbuser:dbpass@{parsed.hostname}:{parsed.port}/dbname'.format(**locals())
        self.assertEqual(mongo_url, config['OMEGA_MONGO_URL'])
        # internal view
        config = get_client_config(self.user, qualifier='default', view=True)
        self.assertIn('OMEGA_CELERY_CONFIG', config)
        self.assertIn('BROKER_URL', config['OMEGA_CELERY_CONFIG'])
        self.assertEqual(defaults.OMEGA_BROKER, config['OMEGA_CELERY_CONFIG']['BROKER_URL'])
        self.assertIn('OMEGA_MONGO_URL', config)
        parsed = urlparse(defaults.OMEGA_MONGO_URL)
        mongo_url = 'mongodb://dbuser:dbpass@{parsed.hostname}:{parsed.port}/dbname'.format(**locals())
        self.assertEqual(mongo_url, config['OMEGA_MONGO_URL'])

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

