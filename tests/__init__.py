import unittest
import re

from osv import osv, fields
from mongodb_backend import testing, osv_mongodb
from expects import *
from destral.transaction import Transaction

from mongodb_backend import mongodb2
from mongodb_backend import orm_mongodb


class TestTranslateDomain(unittest.TestCase):

    def test_translate_domain(self):
        mdbconn = mongodb2.MDBConn()
        res = mdbconn.translate_domain([('name', '=', 'ol')])
        self.assertEqual(res, {'name': 'ol'})

        res = mdbconn.translate_domain([('name', '!=', 'ol')])
        self.assertEqual(res, {'name': {'$ne': 'ol'}})

        res = mdbconn.translate_domain([('name', 'like', 'ol%')])
        self.assertEqual(res, {'name': {'$regex': re.compile('ol.*')}})

        res = mdbconn.translate_domain([('name', 'not like', '%ol%')])
        self.assertEqual(res, {'name': {'$not': re.compile('.*ol.*')}})

        res = mdbconn.translate_domain([('name', 'ilike', '%ol%')])
        self.assertEqual(res, {'name': re.compile('.*ol.*', re.IGNORECASE)})

        res = mdbconn.translate_domain([('name', 'not ilike', '%ol%')])
        self.assertEqual(res, {'name': {'$not': re.compile('.*ol.*', re.IGNORECASE)}})

        res = mdbconn.translate_domain([('_id', 'in', [1, 2, 3])])
        self.assertEqual(res, {'_id': {'$in': [1, 2, 3]}})

        res = mdbconn.translate_domain([('_id', 'not in', [1, 2, 3])])
        self.assertEqual(res, {'_id': {'$nin': [1, 2, 3]}})

        res = mdbconn.translate_domain([('_id', '<=', 10)])
        self.assertEqual(res, {'_id': {'$lte': 10}})

        res = mdbconn.translate_domain([('_id', '<', 10)])
        self.assertEqual(res, {'_id': {'$lt': 10}})

        res = mdbconn.translate_domain([('_id', '>=', 10)])
        self.assertEqual(res, {'_id': {'$gte': 10}})

        res = mdbconn.translate_domain([('_id', '>', 10)])
        self.assertEqual(res, {'_id': {'$gt': 10}})

        res = mdbconn.translate_domain([('_id', '>', 10), ('_id', '<', 15)])
        self.assertEqual(res, {'_id': {'$gt': 10, '$lt': 15}})

        res = mdbconn.translate_domain([
            ('_id', '>', 10),
            ('_id', '<', 15),
            ('name', 'ilike', '%ol%')
        ])
        self.assertEqual(res, {'_id': {'$gt': 10, '$lt': 15}, 'name': re.compile('.*ol.*', re.IGNORECASE)})


def test_compute_order_parsing(self):
    class order_test(orm_mongodb.orm_mongodb):
        _name = 'order.test'

    with Transaction().start(self.database) as txn:
        cursor = txn.cursor
        uid = txn.user

        testing_class = order_test(cursor)

        res = testing_class._compute_order(cursor, uid, 'test desc')
        self.assertEqual(res, [('test', -1)])

        res = testing_class._compute_order(cursor, uid, 'test asc')
        self.assertEqual(res, [('test', 1)])

        res = testing_class._compute_order(cursor, uid, 'test desc, '
                                                        'test2 desc')
        self.assertEqual(res, [('test', -1), ('test2', -1)])

        res = testing_class._compute_order(cursor, uid, 'test asc, '
                                                        'test2 desc')
        self.assertEqual(res, [('test', 1), ('test2', -1)])


class MongoModelTest(osv_mongodb.osv_mongodb):
    _name = 'mongomodel.test'

    _columns = {
        'name': fields.char('Name', size=64),
        'other_name': fields.char('Other name', size=64)
    }


class MongoDBBackendTest(testing.MongoDBTestCase):

    @unittest.skip('No views defined in this module')
    def test_all_views(self):
        pass
    
    @unittest.skip('No access rules defined')
    def test_access_rules(self):
        pass

    def test_mdbpool(self):
        from mongodb_backend.mongodb2 import mdbpool
        expect(mdbpool._connection).to(be_none)

        # If we try to access to the connection mongodb connects
        expect(mdbpool.connection).to_not(be_none)

    def test_default_mongodb_name(self):
        from mongodb_backend.mongodb2 import mdbpool
        expect(self.openerp.config.options).to_not(have_keys(
            'mongodb_name',
            'mongodb_port',
            'mongodb_host',
            'mongodb_user',
            'mongodb_pass'
        ))
        # After accessing to getting object variables are defined
        db = mdbpool.get_db()
        expect(self.openerp.config.options).to(have_keys(
            mongodb_name=self.database
        ))


class MongoDBORMTests(testing.MongoDBTestCase):

    def setUp(self):
        self.txn = Transaction().start(self.database)

    def tearDown(self):
        self.txn.stop()

    def create_model(self):
        cursor = self.txn.cursor
        MongoModelTest()
        osv.class_pool[MongoModelTest._name].createInstance(
            self.openerp.pool, 'mongodb_backend', cursor
        )
        mmt_obj = self.openerp.pool.get(MongoModelTest._name)
        mmt_obj._auto_init(cursor)

    def test_name_get(self):
        self.create_model()
        cursor = self.txn.cursor
        uid = self.txn.user
        mmt_obj = self.openerp.pool.get(MongoModelTest._name)
        mmt_id = mmt_obj.create(cursor, uid, {
            'name': 'Foo',
            'other_name': 'Bar'
        })

        result = mmt_obj.name_get(cursor, uid, [mmt_id])
        self.assertListEqual(
            result,
            [(mmt_id, 'Foo')]
        )

        # Changing the rec_name should use other field
        MongoModelTest._rec_name = 'other_name'
        result = mmt_obj.name_get(cursor, uid, [mmt_id])
        self.assertListEqual(
            result,
            [(mmt_id, 'Bar')]
        )
