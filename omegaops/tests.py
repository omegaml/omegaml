from django.test.testcases import TestCase

from omegaops import add_user
from pymongo.errors import PyMongoError, OperationFailure


class OmegaOpsTest(TestCase):

    def setUp(self):
        TestCase.setUp(self)

    def tearDown(self):
        TestCase.tearDown(self)

    def test_adduser(self):
        dbname = 'testdbops'
        username = 'testuserops'
        password = 'foobar'
        db = add_user(dbname, username, password)
        self.assertIsNotNone(db)
        # check we can authenticate and insert
        db.authenticate(username, password)
        coll = db['data']
        coll.insert({'foo': 'bar'})
        # check no other user can authenticate
        with self.assertRaises(PyMongoError) as ex:
            db.authenticate('sillyuser', 'norealpassword')
        dbname2 = 'testdbops2'
        username2 = 'testuserops2'
        password2 = 'foobar2'
        db2 = add_user(dbname2, username2, password2)
        with self.assertRaises(PyMongoError) as ex:
            db.authenticate(username2, password2)
        # check a valid user cannot get access to another db
        db2.authenticate(username2, password2)
        otherdb = db2.client[dbname]
        with self.assertRaises(OperationFailure) as ex:
            otherdb.collection_names()
        