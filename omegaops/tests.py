from django.contrib.auth.models import User
from django.test.testcases import TestCase
from landingpage.models import ServicePlan
from pymongo.errors import PyMongoError, OperationFailure

from omegaops import add_service_deployment, add_userdb


class OmegaOpsTest(TestCase):
    def setUp(self):
        TestCase.setUp(self)
        self.username = username = 'testuser@omegaml.io'
        self.email = email = 'testuser@omegaml.io'
        self.password = password = 'password'
        self.user = User.objects.create_user(username, email, password)

    def tearDown(self):
        TestCase.tearDown(self)

    def test_adduserdb(self):
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
