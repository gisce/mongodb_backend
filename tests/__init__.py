import unittest
import re

from osv import osv, fields
from mongodb_backend import testing, osv_mongodb
from expects import *
from destral.transaction import Transaction
from mongodb_backend import fields as mdb_fields

from mongodb_backend import mongodb2
from mongodb_backend import orm_mongodb
import datetime


class TestTranslateDomain(unittest.TestCase):

    def test_translate_domain(self):
        mdbconn = mongodb2.MDBConn()
        res = mdbconn.translate_domain([('name', '=', 'ol')])
        self.assertIn(res, ({'name': 'ol'}, {'name': {'$eq': 'ol'}}))

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
        'other_name': fields.char('Other name', size=64),
        'boolean_field': fields.boolean('Boolean Field', size=64),
        'integer_field_with_index': fields.integer('Integer Field', select=1),
        'file_example': fields.binary('test', gridfs=True),
        'date_field': fields.date('Date Field'),
        'datetime_field': fields.datetime('Datetime Field'),
        'function_field': fields.function(
            lambda self, cursor, uid, ids, *a, **k:
            {_id: 'test' for _id in (ids if isinstance(ids, (list, tuple)) else [ids])},
            string='func', type='text', method=True, store=False
        ),
        'function_field_multi': fields.function(
            lambda self, cursor, uid, ids, *a, **k:
            {_id: {'function_field_multi': 'test'} for _id in (ids if isinstance(ids, (list, tuple)) else [ids])},
            string='func mult', type='text', method=True, store=False, multi='test'
        ),
    }
    _defaults = {
        'date_field': lambda *a: '2024-01-01',
        'integer_field_with_index': lambda *a: 1
    }


class NoMongoModelTestWithGridFs(osv.osv):
    _name = 'no.mongomodel.test.with.gridfs'

    _columns = {
        'name': fields.char('Name', size=64),
        'file_example': mdb_fields.gridfs('test')
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
        self.cleanup()
        self.txn.stop()

    def cleanup(self):
        from mongodb_backend.mongodb2 import mdbpool
        db = mdbpool.get_db()
        db.drop_collection("mongomodel_test")

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
            'other_name': 'Bar',
            'boolean_field': True
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

    def test_boolean(self):
        self.create_model()
        cursor = self.txn.cursor
        uid = self.txn.user
        mmt_obj = self.openerp.pool.get(MongoModelTest._name)
        # Create test
        mmt_id = mmt_obj.create(cursor, uid, {
            'name': 'Foo',
            'other_name': 'Bar',
            'boolean_field': True
        })

        readed_value = mmt_obj.read(cursor, uid, mmt_id, ['boolean_field'])['boolean_field']
        expect(readed_value).to(equal(True))

        # write/search "True"
        for value in [True, 1, '1', [1, 2, ]]:
            mmt_obj.write(cursor, uid, [mmt_id], {'boolean_field': value})

            # read
            readed_value = mmt_obj.read(cursor, uid, mmt_id, ['boolean_field'])['boolean_field']
            expect(readed_value).to(equal(True))

            # search Boolean
            m_ids = mmt_obj.search(cursor, uid, [('boolean_field', '=', True)])
            expect(len(m_ids)).to(be_above(0))

            m_ids = mmt_obj.search(cursor, uid, [('boolean_field', '=', False)])
            expect(len(m_ids)).to(equal(0))

        # write/search "False"
        for value in [False, 0, [], None, '']:
            mmt_obj.write(cursor, uid, [mmt_id], {'boolean_field': value})

            # read
            readed_value = mmt_obj.read(cursor, uid, mmt_id, ['boolean_field'])['boolean_field']
            expect(readed_value).to(equal(False))

            # search Boolean
            m_ids = mmt_obj.search(cursor, uid, [('boolean_field', '=', True)])
            expect(len(m_ids)).to(equal(0))

            m_ids = mmt_obj.search(cursor, uid, [('boolean_field', '=', False)])
            expect(len(m_ids)).to(be_above(0))

    def test_create_index_from_select(self):
        self.create_model()
        cursor = self.txn.cursor
        uid = self.txn.user
        mmt_obj = self.openerp.pool.get(MongoModelTest._name)
        # Create test
        mmt_id = mmt_obj.create(cursor, uid, {
            'name': 'Foo',
            'other_name': 'Bar',
            'boolean_field': True,
            'integer_field_with_index': 8
        })
        from mongodb_backend.mongodb2 import mdbpool
        db = mdbpool.get_db()
        collection = db.mongomodel_test
        self.assertIn('integer_field_with_index_1', collection.index_information())

    def test_orm_operation(self):
        self.create_model()
        cursor = self.txn.cursor
        uid = self.txn.user
        mmt_obj = self.openerp.pool.get(MongoModelTest._name)
        import uuid
        unique_ident = '{}'.format(uuid.uuid4())

        # Test create
        mmt_id = mmt_obj.create(cursor, uid, {
            'name': unique_ident,
            'other_name': 'Bar',
            'boolean_field': True,
            'integer_field_with_index': 8
        })
        self.assertTrue(mmt_id)

        # Test search
        found_ids = mmt_obj.search(cursor, uid, [('name', '=', unique_ident)])
        self.assertTrue(found_ids)
        self.assertIn(mmt_id, found_ids)
        self.assertEqual(len(found_ids), 1)

        # Test write/read
        mmt_obj.write(cursor, uid, found_ids, {'other_name': unique_ident})
        field_content = mmt_obj.read(cursor, uid, mmt_id, ['other_name'])['other_name']
        self.assertEqual(field_content, unique_ident)
        all_content = mmt_obj.read(cursor, uid, mmt_id, None)
        expected_content = {
            'name': unique_ident, 'date_field': '2024-01-01',
            'boolean_field': True, 'integer_field_with_index': 8,
            'other_name': unique_ident, 'id': mmt_id, 'function_field': 'test',
            'function_field_multi': 'test'
        }
        self.assertEqual(all_content, expected_content)


        # Test Unlink
        mmt_obj.unlink(cursor, uid, found_ids)
        found_ids = mmt_obj.search(cursor, uid, [('name', '=', unique_ident)])
        self.assertFalse(found_ids)

    def test_binary(self):
        from addons import get_module_resource
        import uuid
        from base64 import b64encode, b64decode
        self.create_model()
        cursor = self.txn.cursor
        uid = self.txn.user
        mmt_obj = self.openerp.pool.get(MongoModelTest._name)

        unique_ident = '{}'.format(uuid.uuid4())

        image_path = get_module_resource(
            'mongodb_backend', 'tests', 'fixtures', '15796004.png'
        )

        with open(image_path, 'rb') as image_fd:
            fb = image_fd.read()

        mmt_id = mmt_obj.create(cursor, uid, {
            'name': unique_ident,
            'other_name': 'Bar',
            'boolean_field': True,
            'integer_field_with_index': 8,
            'file_example': b64encode(fb)
        })
        res_file = mmt_obj.read(cursor, uid, mmt_id, ['file_example'])['file_example']
        self.assertEqual(b64decode(res_file), fb)

        mmt_obj.write(cursor, uid, [mmt_id], {'file_example': b64encode(fb)})
        res_file = mmt_obj.read(cursor, uid, mmt_id, ['file_example'])['file_example']
        self.assertEqual(b64decode(res_file), fb)

    def test_gridfs(self):
        from addons import get_module_resource
        from base64 import b64encode, b64decode
        cursor = self.txn.cursor
        uid = self.txn.user
        NoMongoModelTestWithGridFs()
        osv.class_pool[NoMongoModelTestWithGridFs._name].createInstance(
            self.openerp.pool, 'mongodb_backend', cursor
        )
        mmt_obj = self.openerp.pool.get(NoMongoModelTestWithGridFs._name)
        mmt_obj._auto_init(cursor)

        image_path = get_module_resource(
            'mongodb_backend', 'tests', 'fixtures', '15796004.png'
        )

        with open(image_path, 'rb') as image_fd:
            fb = image_fd.read()

        mmt_id = mmt_obj.create(cursor, uid, {
            'name': 'test',
            'file_example': b64encode(fb)
        })

        mmt_obj.write(cursor, uid, [mmt_id], {'file_example': b64encode(fb)})
        res_file = mmt_obj.read(cursor, uid, mmt_id, ['file_example'])['file_example']
        self.assertEqual(b64decode(res_file), fb)

    def test_dates(self):
        self.create_model()
        cursor = self.txn.cursor
        uid = self.txn.user
        mmt_obj = self.openerp.pool.get(MongoModelTest._name)
        import uuid

        expected_date_str = '2022-12-31'
        expected_datetime_str = '2022-12-31 12:00:00'

        unique_ident2 = '{}'.format(uuid.uuid4())

        mmt2_id = mmt_obj.create(cursor, uid, {
            'name': unique_ident2,
            'date_field': expected_date_str,
            'datetime_field': expected_datetime_str
        })

        res2 = mmt_obj.read(cursor, uid, mmt2_id, ['date_field', 'datetime_field'])
        self.assertEqual(res2['date_field'], expected_date_str)
        self.assertEqual(res2['datetime_field'], expected_datetime_str)

        expected_datetime_str_2 = '2023-12-31 00:00:00'
        write_value = '2023-12-31'

        mmt_obj.write(cursor, uid, [mmt2_id], {'datetime_field': write_value})
        res2 = mmt_obj.read(cursor, uid, mmt2_id, ['datetime_field'])
        self.assertEqual(res2['datetime_field'], expected_datetime_str_2)

    def test_export_data(self):
        from base64 import b64encode, b64decode
        from io import BytesIO
        import pandas as pd
        self.create_model()
        cursor = self.txn.cursor
        uid = self.txn.user
        mmt_obj = self.openerp.pool.get(MongoModelTest._name)
        import uuid
        unique_ident = '{}'.format(uuid.uuid4())

        # Test create
        mmt_id = mmt_obj.create(cursor, uid, {
            'name': unique_ident,
            'other_name': 'Bar',
            'boolean_field': True,
            'integer_field_with_index': 8
        })
        unique_ident2 = '{}'.format(uuid.uuid4())
        mmt2_id = mmt_obj.create(cursor, uid, {
            'name': unique_ident2,
            'other_name': 'Bar2',
            'boolean_field': False,
            'integer_field_with_index': 4
        })
        res_csv = mmt_obj.export_data2(
            cursor, uid, [], 100, ['name', 'other_name', 'boolean_field'], 'csv', {'prefetch': False}
        )
        csv_f = BytesIO(b64decode(res_csv['datas']))
        res_excel = mmt_obj.export_data2(
            cursor, uid, [], 100, ['name', 'other_name', 'boolean_field'], 'xlsx', {'prefetch': False}
        )
        xlsx_f = BytesIO(b64decode(res_excel['datas']))
        df_csv = pd.read_csv(csv_f, sep=';')
        df_xlsx = pd.read_excel(xlsx_f)
        self.assertEqual(df_csv['Name'].tolist(), [unique_ident, unique_ident2])
        self.assertEqual(df_xlsx['Name'].tolist(), [unique_ident, unique_ident2])

    def test_order(self):
        self.create_model()
        cursor = self.txn.cursor
        uid = self.txn.user
        mmt_obj = self.openerp.pool.get(MongoModelTest._name)
        import uuid
        unique_ident = '{}'.format(uuid.uuid4())

        # Test create
        mmt_id = mmt_obj.create(cursor, uid, {
            'name': unique_ident,
            'other_name': 'Bar',
            'boolean_field': True,
            'integer_field_with_index': 7
        })

        unique_ident2 = '{}'.format(uuid.uuid4())

        # Test create
        mmt_id_2 = mmt_obj.create(cursor, uid, {
            'name': unique_ident2,
            'other_name': 'Bar1',
            'integer_field_with_index': 8
        })

        unique_ident3 = '{}'.format(uuid.uuid4())

        # Test create
        mmt_id_3 = mmt_obj.create(cursor, uid, {
            'name': unique_ident3,
            'other_name': 'Bar2',
            'integer_field_with_index': 5
        })

        unique_ident4 = '{}'.format(uuid.uuid4())

        mmt_id_4 = mmt_obj.create(cursor, uid, {
            'name': unique_ident4,
            'other_name': 'Bar4',
            'integer_field_with_index': 5
        })
        res = mmt_obj.search(cursor, uid, [])
        self.assertEqual(res, [mmt_id, mmt_id_2, mmt_id_3, mmt_id_4])

        res = mmt_obj.search(cursor, uid, [('name', '!=', False)])
        self.assertEqual(res, [mmt_id, mmt_id_2, mmt_id_3, mmt_id_4])

        # mmt_id_4 and mmt_id_3 has de same integer_field_with_index.
        # On mongo if id desc not provided returns mmt_id_2, mmt_id, mmt_id_4, mmt_id_3
        # but in ferretDB returns mmt_id_2, mmt_id, mmt_id_3, mmt_id_4
        # To avoid discordance we force id desc as secondary order
        res = mmt_obj.search(cursor, uid, [('name', '!=', False)], order='integer_field_with_index desc, id desc')
        self.assertEqual(res, [mmt_id_2, mmt_id, mmt_id_4, mmt_id_3])

        res = mmt_obj.search(cursor, uid, [('name', '!=', False)], order='integer_field_with_index asc')
        self.assertEqual(res, [mmt_id_3, mmt_id_4, mmt_id, mmt_id_2])

        res = mmt_obj.search(cursor, uid, [('name', '!=', False)], order='integer_field_with_index asc, other_name desc')
        self.assertEqual(res, [mmt_id_4, mmt_id_3, mmt_id, mmt_id_2])

    def test_datetime_search(self):
        self.create_model()
        cursor = self.txn.cursor
        uid = self.txn.user
        mmt_obj = self.openerp.pool.get(MongoModelTest._name)
        import uuid
        unique_ident = '{}'.format(uuid.uuid4())

        # Test create
        mmt_id = mmt_obj.create(cursor, uid, {
            'name': unique_ident,
            'other_name': 'Bar',
            'datetime_field': '2025-05-05 02:00:00',
            'date_field': '2025-05-05'
        })

        # Test for distinct dates cases

        res = mmt_obj.search(cursor, uid, [('name', '=', unique_ident), ('datetime_field', '<', '2025-05-06')])
        self.assertEqual(res, [mmt_id])

        res = mmt_obj.search(cursor, uid, [('name', '=', unique_ident), ('datetime_field', '>', '2025-05-04')])
        self.assertEqual(res, [mmt_id])

        res = mmt_obj.search(cursor, uid, [('name', '=', unique_ident), ('datetime_field', '<=', '2025-05-06')])
        self.assertEqual(res, [mmt_id])

        res = mmt_obj.search(cursor, uid, [('name', '=', unique_ident), ('datetime_field', '>=', '2025-05-04')])
        self.assertEqual(res, [mmt_id])

        res = mmt_obj.search(cursor, uid, [('name', '=', unique_ident), ('date_field', '<', '2025-05-06')])
        self.assertEqual(res, [mmt_id])

        res = mmt_obj.search(cursor, uid, [('name', '=', unique_ident), ('date_field', '>', '2025-05-04')])
        self.assertEqual(res, [mmt_id])

        res = mmt_obj.search(cursor, uid, [('name', '=', unique_ident), ('date_field', '<=', '2025-05-06')])
        self.assertEqual(res, [mmt_id])

        res = mmt_obj.search(cursor, uid, [('name', '=', unique_ident), ('date_field', '>=', '2025-05-04')])
        self.assertEqual(res, [mmt_id])

        # Tests for same date range

        res = mmt_obj.search(
            cursor, uid, [
                ('name', '=', unique_ident),
                ('datetime_field', '>=', '2025-05-05'), ('datetime_field', '<=', '2025-05-05')
            ]
        )
        self.assertEqual(res, [mmt_id])

        res = mmt_obj.search(
            cursor, uid, [
                ('name', '=', unique_ident),
                ('datetime_field', '>', '2025-05-05'), ('datetime_field', '<', '2025-05-05')
            ]
        )
        self.assertEqual(res, [mmt_id])

        res = mmt_obj.search(
            cursor, uid, [
                ('name', '=', unique_ident),
                ('date_field', '>=', '2025-05-05'), ('date_field', '<=', '2025-05-05')
            ]
        )
        self.assertEqual(res, [mmt_id])

        res = mmt_obj.search(
            cursor, uid, [
                ('name', '=', unique_ident),
                ('date_field', '>', '2025-05-05'), ('date_field', '<', '2025-05-05')
            ]
        )
        self.assertEqual(res, [])

    def test_aggregate_pymongo(self):
        self.create_model()
        cursor = self.txn.cursor
        uid = self.txn.user
        mmt_obj = self.openerp.pool.get(MongoModelTest._name)
        import uuid
        unique_ident = '{}'.format(uuid.uuid4())

        # Test create
        mmt_id = mmt_obj.create(cursor, uid, {
            'name': unique_ident,
            'other_name': 'Bar',
            'boolean_field': True,
            'integer_field_with_index': 7
        })

        unique_ident2 = '{}'.format(uuid.uuid4())

        # Test create
        mmt_id_2 = mmt_obj.create(cursor, uid, {
            'name': unique_ident2,
            'other_name': 'Bar',
            'integer_field_with_index': 8
        })

        unique_ident3 = '{}'.format(uuid.uuid4())

        # Test create
        mmt_id_3 = mmt_obj.create(cursor, uid, {
            'name': unique_ident3,
            'other_name': 'Bar2',
            'integer_field_with_index': 5
        })

        unique_ident4 = '{}'.format(uuid.uuid4())

        # Test create
        mmt_id_3 = mmt_obj.create(cursor, uid, {
            'name': unique_ident4,
            'other_name': 'Bar2',
            'integer_field_with_index': 2
        })
        from mongodb_backend.mongodb2 import mdbpool
        db = mdbpool.get_db()
        collection = db.mongomodel_test
        pipeline = [
            {"$unwind": "$other_name"},
            {"$match": {"integer_field_with_index": {"$gt": 2}}},
            {"$group": {"_id": "$other_name", "count": {"$sum": 1}, "total": {"$sum": "$integer_field_with_index"}}},
            {"$sort": {"total": -1}}
        ]
        res = list(collection.aggregate(pipeline))
        self.assertEqual(
            res,
            [{"_id": "Bar", "total": 15, "count": 2}, {"_id": "Bar2", "total": 5, "count": 1}]
        )
