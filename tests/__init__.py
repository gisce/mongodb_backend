from __future__ import absolute_import, unicode_literals
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
        self.assertEqual(res, {'$and': [{'_id': {'$gt': 10}}, {'_id': {'$lt': 15}}]})

        res = mdbconn.translate_domain([
            ('_id', '>', 10),
            ('_id', '<', 15),
            ('name', 'ilike', '%ol%')
        ])
        self.assertEqual(res, {
            '$and': [
                {'_id': {'$gt': 10}},
                {'_id': {'$lt': 15}},
                {'name': re.compile('.*ol.*', re.IGNORECASE)}
            ]
        })


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

class TestModel(osv_mongodb.osv_mongodb):
    _name = 'comprehensive.domain.model'

    _columns = {
        'name': fields.char('Name', size=64, exact_match=True),
        'num':  fields.integer('Numeric'),
        'flag': fields.boolean('Flag'),
        'day':  fields.date('Day'),
        'moment': fields.datetime('Moment'),
    }
    _defaults = {
        'flag': lambda *a: False
    }

def _mk(model, cursor, uid, **vals):
    import uuid
    _vals = {
        'name': '{}'.format(uuid.uuid4()),
        'num':  0,
        'day':  '2024-01-01',
        'moment': '2024-01-01 00:00:00',
        'flag': False
    }
    _vals.update(vals)
    _id = model.create(cursor, uid, _vals)
    return _id, _vals


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
        # Module installation or previous tests can populate MongoDB defaults in
        # the process-global OpenERP config. Own this test's precondition, but
        # avoid clearing auth-related options: FerretDB runs need those
        # credentials later in MongoDBTestCase.tearDown().
        default_options = (
            'mongodb_name',
            'mongodb_port',
            'mongodb_host',
        )
        original_options = dict(
            (key, self.openerp.config.options[key])
            for key in self.openerp.config.options
            if key in default_options
        )

        def restore_mongodb_options():
            for key in default_options:
                self.openerp.config.options.pop(key, None)
            self.openerp.config.options.update(original_options)

        self.addCleanup(restore_mongodb_options)
        for key in default_options:
            self.openerp.config.options.pop(key, None)
        mdbpool._connection = None

        expect(self.openerp.config.options).to_not(have_keys(
            'mongodb_name',
            'mongodb_port',
            'mongodb_host'
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

        # Test with single id (integer)
        result = mmt_obj.name_get(cursor, uid, mmt_id)
        self.assertListEqual(
            result,
            [(mmt_id, 'Foo')]
        )

        # Test with empty ids
        result = mmt_obj.name_get(cursor, uid, [])
        self.assertListEqual(result, [])

        # Changing the rec_name should use other field
        MongoModelTest._rec_name = 'other_name'
        result = mmt_obj.name_get(cursor, uid, [mmt_id])
        self.assertListEqual(
            result,
            [(mmt_id, 'Bar')]
        )
        # Reset _rec_name to default
        MongoModelTest._rec_name = 'name'

    def test_name_search(self):
        self.create_model()
        cursor = self.txn.cursor
        uid = self.txn.user
        mmt_obj = self.openerp.pool.get(MongoModelTest._name)
        
        # Save original _rec_name
        original_rec_name = MongoModelTest._rec_name
        
        # Create test records
        mmt_id1 = mmt_obj.create(cursor, uid, {
            'name': 'Apple Product',
            'other_name': 'Product A',
            'boolean_field': True
        })
        mmt_id2 = mmt_obj.create(cursor, uid, {
            'name': 'Banana Product',
            'other_name': 'Product B',
            'boolean_field': True
        })
        mmt_id3 = mmt_obj.create(cursor, uid, {
            'name': 'Cherry Product',
            'other_name': 'Product C',
            'boolean_field': False
        })
        
        # Test basic name search with ilike operator (default)
        result = mmt_obj.name_search(cursor, uid, 'Apple')
        self.assertIn((mmt_id1, 'Apple Product'), result)
        self.assertEqual(len(result), 1)
        
        # Test case-insensitive search
        result = mmt_obj.name_search(cursor, uid, 'apple')
        self.assertIn((mmt_id1, 'Apple Product'), result)
        self.assertEqual(len(result), 1)
        
        # Test partial match
        result = mmt_obj.name_search(cursor, uid, 'Product')
        self.assertEqual(len(result), 3)
        result_ids = [r[0] for r in result]
        self.assertIn(mmt_id1, result_ids)
        self.assertIn(mmt_id2, result_ids)
        self.assertIn(mmt_id3, result_ids)
        
        # Test with args (domain filters)
        result = mmt_obj.name_search(cursor, uid, 'Product', 
                                      args=[('boolean_field', '=', True)])
        self.assertEqual(len(result), 2)
        result_ids = [r[0] for r in result]
        self.assertIn(mmt_id1, result_ids)
        self.assertIn(mmt_id2, result_ids)
        self.assertNotIn(mmt_id3, result_ids)
        
        # Test with empty name (should return all records or filtered by args)
        result = mmt_obj.name_search(cursor, uid, '', 
                                      args=[('boolean_field', '=', False)])
        self.assertEqual(len(result), 1)
        self.assertIn((mmt_id3, 'Cherry Product'), result)
        
        # Test with limit
        result = mmt_obj.name_search(cursor, uid, 'Product', limit=2)
        self.assertEqual(len(result), 2)
        
        # Test with exact match operator
        result = mmt_obj.name_search(cursor, uid, 'Apple Product', operator='=')
        self.assertEqual(len(result), 1)
        self.assertIn((mmt_id1, 'Apple Product'), result)
        
        # Test with like operator
        result = mmt_obj.name_search(cursor, uid, 'Banana%', operator='like')
        self.assertEqual(len(result), 1)
        self.assertIn((mmt_id2, 'Banana Product'), result)
        
        # Test with different _rec_name
        try:
            MongoModelTest._rec_name = 'other_name'
            result = mmt_obj.name_search(cursor, uid, 'Product A')
            self.assertIn((mmt_id1, 'Product A'), result)
            self.assertEqual(len(result), 1)
        finally:
            # Always restore original _rec_name
            MongoModelTest._rec_name = original_rec_name

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
            # {"$unwind": "$other_name"},
            {"$match": {"integer_field_with_index": {"$gt": 2}}},
            {"$group": {"_id": "$other_name", "count": {"$sum": 1}, "total": {"$sum": "$integer_field_with_index"}}},
            {"$sort": {"total": -1}}
        ]
        res = list(collection.aggregate(pipeline))
        self.assertEqual(
            res,
            [{"_id": "Bar", "total": 15, "count": 2}, {"_id": "Bar2", "total": 5, "count": 1}]
        )


class TranslateDomainComprehensive(testing.MongoDBTestCase):

    def setUp(self):
        self.mdb = mongodb2.MDBConn()

    def _assert(self, domain, expected):
        res = self.mdb.translate_domain(domain)
        self.assertEqual(res, expected)

    def test_simple_operators(self):
        self._assert([('x', '=', 5)],            {'x': {'$eq': 5}})
        self._assert([('x', '!=', 5)],           {'x': {'$ne': 5}})
        self._assert([('x', '>', 5)],            {'x': {'$gt': 5}})
        self._assert([('x', '>=', 5)],           {'x': {'$gte': 5}})
        self._assert([('x', '<', 5)],            {'x': {'$lt': 5}})
        self._assert([('x', '<=', 5)],           {'x': {'$lte': 5}})
        self._assert([('x', 'in', [1, 2])],      {'x': {'$in': [1, 2]}})
        self._assert([('x', 'not in', [1, 2])],  {'x': {'$nin': [1, 2]}})

    def test_like_variants(self):
        self._assert([('name', 'like', 'fo%')],
                     {'name': {'$regex': re.compile('fo.*')}})
        self._assert([('name', 'not like', '%fo%')],
                     {'name': {'$not': re.compile('.*fo.*')}})
        self._assert([('name', 'ilike', '%fo%')],
                     {'name': re.compile('.*fo.*', re.I)})
        self._assert([('name', 'not ilike', '%fo%')],
                     {'name': {'$not': re.compile('.*fo.*', re.I)}})

    def test_and_or_not_flat(self):
        dom = [
            '|',
              ('a', '=', 1),
              ('b', '>', 2)
        ]
        exp = {'$or': [{'a': {'$eq': 1}}, {'b': {'$gt': 2}}]}
        self._assert(dom, exp)

        dom = [
            '&',
              ('a', '=', 1),
              ('b', '<', 5)
        ]
        exp = {'$and': [{'a': {'$eq': 1}}, {'b': {'$lt': 5}}]}
        self._assert(dom, exp)

        dom = ['!', ('a', '=', 1)]
        exp = {'$nor': [{'a': {'$eq': 1}}]}
        self._assert(dom, exp)

    def test_and_implicit_multiple_leaves(self):
        dom = [('a', '=', 1), ('b', '>', 2)]
        exp = {'$and': [{'a': {'$eq': 1}}, {'b': {'$gt': 2}}]}
        self._assert(dom, exp)

    def test_nested_sub_lists(self):
        dom = [
            '|',
              ('a', '=', 1),
              [
                  '&',
                    ('b', '>', 2),
                    ('c', '<', 10)
              ]
        ]
        exp = {
            '$or': [
                {'a': {'$eq': 1}},
                {'$and': [{'b': {'$gt': 2}}, {'c': {'$lt': 10}}]}
            ]
        }
        self._assert(dom, exp)


class MongoDomainCombinations(testing.MongoDBTestCase):

    def setUp(self):
        self.tx = Transaction().start(self.database)
        cursor = self.tx.cursor
        TestModel()
        osv.class_pool[TestModel._name].createInstance(
            self.openerp.pool, 'mongodb_backend', cursor
        )
        self.obj = self.openerp.pool.get(TestModel._name)
        self.obj._auto_init(cursor)

        uid = self.tx.user
        self.r1, v1 = _mk(self.obj, cursor, uid,
                          name='FOO', num=1, flag=False,
                          day='2025-05-05', moment='2025-05-05 02:00:00')
        self.r2, v2 = _mk(self.obj, cursor, uid,
                          name='BAR', num=7, flag=True,
                          day='2025-05-06', moment='2025-05-06 20:00:00')
        self.r3, v3 = _mk(self.obj, cursor, uid,
                          name='BAZ', num=5, flag=False,
                          day='2025-05-04', moment='2025-05-04 23:00:00')

    def tearDown(self):
        from mongodb_backend.mongodb2 import mdbpool
        mdbpool.get_db().drop_collection("comprehensive_domain_model")
        self.tx.stop()

    # --------------------------------------------------------------
    #  BOOLEAN and EXACT_MATCH
    # --------------------------------------------------------------
    def test_boolean_and_exact_match(self):
        c, u = self.tx.cursor, self.tx.user

        # exact_match: debe ser coincidencia exacta (no regex)
        ids = self.obj.search(c, u, [('name', '=', 'FOO')])
        self.assertEqual(ids, [self.r1])

        # booleano
        ids = self.obj.search(c, u, [('flag', '=', True)])
        self.assertEqual(set(ids), {self.r2})

        ids = self.obj.search(c, u, [('flag', '=', False)])
        self.assertEqual(set(ids), {self.r1, self.r3})

    # --------------------------------------------------------------
    #  Complex logic operators
    # --------------------------------------------------------------
    def test_or_and_not(self):
        c, u = self.tx.cursor, self.tx.user

        dom = [
            '|',
              ('name', '=', 'FOO'),
              ('num', '>', 6)
        ]
        ids = self.obj.search(c, u, dom)
        self.assertEqual(set(ids), {self.r1, self.r2})

        dom = [
            '&',
              ('num', '>', 1),
              ('num', '<', 6)
        ]
        ids = self.obj.search(c, u, dom)
        self.assertEqual(set(ids), {self.r3})

        dom = ['!', ('name', 'ilike', '%A%')]
        ids = self.obj.search(c, u, dom)
        self.assertEqual(set(ids), {self.r1})

    # --------------------------------------------------------------
    #  Dates and Datetimes
    # --------------------------------------------------------------
    def test_date_range_implicit_time(self):
        c, u = self.tx.cursor, self.tx.user
        #  < '2025-05-06' -> 2025-05-06 23:59:59  (include r2)
        dom = [('moment', '<', '2025-05-06')]
        ids = self.obj.search(c, u, dom)
        # This is a rare case. With https://github.com/gisce/mongodb_backend/pull/49
        # 2025-05-06 is treated as 2025-05-06 23:59:59 and 2025-05-06 20:00:00
        # in included in the search result.
        # self.assertEqual(set(ids), {self.r1, self.r3})
        self.assertEqual(set(ids), {self.r1, self.r2, self.r3})

        # >= '2025-05-06' -> 2025-05-06 00:00:00 (only r2)
        dom = [('moment', '>=', '2025-05-06')]
        ids = self.obj.search(c, u, dom)
        self.assertEqual(set(ids), {self.r2})

    # --------------------------------------------------------------
    # NESTED AND IMPLICIT MULTI-SHEET JOIN
    # --------------------------------------------------------------
    def test_nested_combination(self):
        c, u = self.tx.cursor, self.tx.user
        dom = [
            '|',
              ('name', '=', 'FOO'),
              [
                  '&',
                    ('num', '>', 4),
                    ('flag', '=', True)
              ]
        ]
        ids = self.obj.search(c, u, dom)
        self.assertEqual(set(ids), {self.r1, self.r2})