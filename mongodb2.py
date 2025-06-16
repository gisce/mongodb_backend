# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP - MongoDB backend
#    Copyright (C) 2011 Joan M. Grande
#    Thanks to Sharoon Thomas for the operator mapping code
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
from __future__ import unicode_literals
from six import string_types
import tools
from pymongo import MongoClient
from pymongo.errors import AutoReconnect
from pymongo.read_preferences import ReadPreference
import re
import netsvc
from osv.orm import except_orm
from time import sleep
from .misc import pattern_type


logger = netsvc.Logger()


class MDBConn(object):

    OPERATOR_MAPPING = {
        '=': lambda l1, l3: {l1: {'$eq': l3}},
        '!=': lambda l1, l3: {l1: {'$ne': l3}},
        '<=': lambda l1, l3: {l1: {'$lte': l3}},
        '>=': lambda l1, l3: {l1: {'$gte': l3}},
        '<': lambda l1, l3: {l1: {'$lt': l3}},
        '>': lambda l1, l3: {l1: {'$gt': l3}},

        'in': lambda l1, l3: {l1: {'$in': l3}},
        'not in': lambda l1, l3: {l1: {'$nin': l3}},

        'like': lambda l1, l3: {l1: {
            '$regex': re.compile(l3.replace('%', '.*'))}},
        'not like': lambda l1, l3: {l1: {
        '$not': re.compile('%s' % l3.replace('%', '.*'))}},
        'ilike': lambda l1, l3: {l1: re.compile(l3.replace('%', '.*'), re.I)},
        'not ilike': lambda l1, l3: {l1: {
        '$not': re.compile(l3.replace('%', '.*'), re.I)}},
        }

    def translate_domain(self, domain, orm_obj=None):
        """
            Convert an **domain** written in Polish notation (prefix form)
            into an equivalent **MongoDB filter**.

            Parameters
            ----------
            domain : list
                A domain in Odoo format.  It may contain:

                * Leaf conditions written either as tuples
                  ``('field', 'operator', value)`` **or** lists
                  ``['field', 'operator', value]``.
                * Logical operators applied in *prefix* order:

                      | → logical OR (exactly two children expected)
                      & → logical AND (exactly two children expected)
                      ! → logical NOT (exactly one child expected)

                * Arbitrary nesting using sub-lists, e.g.
                  ``['|', ('a', '=', 1), ['&', ('b', '>', 5), ('c', '<', 10)]]``

            orm_obj : orm_mongodb (optional)
                If provided, extra type-specific conversions are applied
                **before** the Mongo filter is built:

                * *Date / datetime*: incoming strings are converted to `datetime`
                  objects; bare dates in ``<, <=, >, >=`` predicates are expanded
                  to *00:00:00* or *23:59:59* so that the semantic matches.
                * *Boolean*: truthy / falsy values are normalized to `True`/`False`.
                * *exact_match* fields: for columns declared with the custom
                  attribute ``exact_match=True`` any regular-expression value that
                  still starts/ends with ``.*`` is stripped (“ilike” always
                  wraps wildcards, but an exact match should not include them).

            Returns
            -------
            dict
                A MongoDB query document using ``$eq``, ``$gt``, ``$lte``, ``$or``,
                ``$and``, ``$nor`` … ready to be passed to
                ``collection.find(filter, …)``.

            Raises
            ------
            ValueError
                If an unrecognized token is encountered (e.g., malformed domain).

            Notes
            -----
            * **The input list is consumed / mutated** (tokens are popped).
              Callers that still need the original domain should pass
              ``copy.deepcopy(domain)`` instead.
            * Consecutive leaf conditions without an explicit logical operator are
              combined with an **implicit AND**, mimicking behavior.
            """
        # ---------- Helper: convert a single leaf ---------------------------
        def _build_leaf(leaf):
            field, op, val = leaf
            # Optional type coercions that depend on the model definition
            if orm_obj is not None:
                # ---- Date / Datetime coercion --------------------------------
                if field in orm_obj.get_date_fields():
                    if (orm_obj._columns[field]._type == 'datetime'
                            and isinstance(val, string_types) and len(val) == 10):
                        # Bare date on a datetime column → expand time component
                        if op in ('>', '>='):
                            val += ' 00:00:00'
                        elif op in ('<', '<='):
                            val += ' 23:59:59'
                    val = orm_obj.transform_date_field(field, val, 'write')
                # ---- Boolean coercion ----------------------------------------
                if field in orm_obj.get_bool_fields():
                    val = bool(val)

                # ---- exact_match cleanup -------------------------------------
                col = orm_obj._columns.get(field)
                if col and getattr(col, 'exact_match', False):
                    import re
                    if isinstance(val, pattern_type):
                        val = val.pattern.lstrip('.*').rstrip('.*')

            return self.OPERATOR_MAPPING[op](field, val)

        # ---------- Helper: recursive‐descent parser ------------------------
        def _parse(tokens):
            """
            Consume *tokens* (list) from the left, return a MongoDB filter
            for the first complete expression found.
            """
            if not tokens:
                return {}

            tok = tokens.pop(0)

            # 1. Logical operators in prefix form
            if tok == '|':
                return {'$or': [_parse(tokens), _parse(tokens)]}
            if tok == '&':
                return {'$and': [_parse(tokens), _parse(tokens)]}
            if tok == '!':
                return {'$nor': [_parse(tokens)]}

            # 2. Leaf (tuple or list)  ('field', 'op', value)
            if (isinstance(tok, (list, tuple))
                    and len(tok) == 3
                    and isinstance(tok[1], string_types)):
                return _build_leaf(tok)

            # 3. Sub-list without an explicit operator ⇒ implicit AND
            if isinstance(tok, list):
                sub_tokens = list(tok)  # work on a copy
                sub_filters = []
                while sub_tokens:
                    sub_filters.append(_parse(sub_tokens))
                return sub_filters[0] if len(sub_filters) == 1 \
                    else {'$and': sub_filters}

            raise ValueError('Domain Token not supported: %s' % tok)

        # --------------------------------------------------------------------

        tokens = list(domain)
        filters = []
        while tokens:
            filters.append(_parse(tokens))

        if not filters:
            return {}
        if len(filters) == 1:
            return filters[0]
        return {'$and': filters}

    @property
    def uri(self):
        """ Mongo uri calculation with backward compatibility prior to 0.4v
        """
        def_db = tools.config.get('db_name', 'openerp')
        tools.config['mongodb_force_uri'] = tools.config.get('mongodb_force_uri', '')
        tools.config['mongodb_force_uri_readonly'] = tools.config.get('mongodb_force_uri_readonly', '')
        tools.config['db_readonly'] = tools.config.get('db_readonly', False)

        tools.config['mongodb_user_readonly'] = tools.config.get('mongodb_user_readonly', '')
        tools.config['mongodb_user_readonly_pass'] = tools.config.get('mongodb_user_readonly_pass', '')
        tools.config['mongodb_user'] = tools.config.get('mongodb_user', '')
        tools.config['mongodb_pass'] = tools.config.get('mongodb_pass', '')

        if tools.config['db_readonly']:

            if not tools.config['mongodb_user_readonly'] and not tools.config['mongodb_force_uri_readonly']:
                logger.notifyChannel(
                    'MongoDB', netsvc.LOG_WARNING,
                    (
                        "No se ha configurado ningun usuario de solo lectura "
                        "ni tampoco una URI especificada para readonly "
                        "las operacions de escritura no estan protegidas"
                    )
                )
            elif not tools.config['mongodb_force_uri_readonly']:
                tools.config['mongodb_user'] = tools.config['mongodb_user_readonly']
                tools.config['mongodb_pass'] = tools.config['mongodb_user_readonly_pass']

        if tools.config['mongodb_force_uri']:
            uri = tools.config['mongodb_force_uri']

        else:
            tools.config['mongodb_ssl'] = tools.config.get('mongodb_ssl', False)
            tools.config['mongodb_name'] = tools.config.get('mongodb_name', def_db)
            tools.config['mongodb_port'] = tools.config.get('mongodb_port', '27017')
            tools.config['mongodb_host'] = tools.config.get('mongodb_host', '')

            tools.config['mongodb_uri'] = tools.config.get(  # Default
                'mongodb_uri',
                (
                    'mongodb://localhost:27017/'
                    if not tools.config['mongodb_ssl']
                    else 'mongodb://localhost:27017/?ssl=true'
                )
            )

            """
                MONGODB-CR  - mongo 2.4, 2.6 - defecto para mantener compatibilidad
                SCRAM-SHA-1 - mongo 3.x
            """
            tools.config['mongodb_auth'] = tools.config.get('mongodb_auth',
                                                            'MONGODB-CR')

            uri = tools.config['mongodb_uri']  # with replicaset must use uri
            if not tools.config.get('mongodb_replicaset', False):
                if tools.config['mongodb_user']:
                    # Auth
                    if tools.config['mongodb_ssl']:
                        uri_tmpl = 'mongodb://%s:%s@%s:%s/%s?ssl=true&authMechanism=%s'
                    else:
                        uri_tmpl = 'mongodb://%s:%s@%s:%s/%s?authMechanism=%s'
                    uri = uri_tmpl % (tools.config['mongodb_user'],
                                      tools.config['mongodb_pass'],
                                      tools.config['mongodb_host'],
                                      tools.config['mongodb_port'],
                                      tools.config['mongodb_name'],
                                      tools.config['mongodb_auth'])
                elif tools.config['mongodb_host']:
                    # No auth
                    if tools.config['mongodb_ssl']:
                        uri_tmpl = 'mongodb://%s:%s/?ssl=true'
                    else:
                        uri_tmpl = 'mongodb://%s:%s/'

                    uri = uri_tmpl % (tools.config['mongodb_host'],
                                      int(tools.config['mongodb_port']))
        return uri

    def mongo_connect(self):
        '''Connects to mongo'''
        try:
            tools.config['mongodb_replicaset'] = tools.config.get(
                'mongodb_replicaset', False
            )
            mongo_client = MongoClient
            kwargs = {}
            if tools.config['mongodb_replicaset']:
                kwargs.update({'replicaSet': tools.config['mongodb_replicaset'],
                               'read_preference': ReadPreference.SECONDARY_PREFERRED})

            connection = mongo_client(self.uri, **kwargs)
        except Exception as e:
            raise except_orm('MongoDB connection error', e)
        return connection

    def __init__(self):
        self._connection = None

    @property
    def connection(self):
        if self._connection is None:
            self._connection = self.mongo_connect()
        return self._connection

    def get_collection(self, collection):

        try:
            db = self.connection[tools.config['mongodb_name']]
            collection = db[collection]

        except AutoReconnect as ar_e:
            max_tries = 5
            count = 0
            while count < max_tries:
                try:
                    logger.notifyChannel('MongoDB', netsvc.LOG_WARNING,
                                 'trying to reconnect...')
                    con = self.mongo_connect()

                    db = con[tools.config['mongodb_name']]
                    collection = db[collection]
                    break
                except AutoReconnect:
                    count += 1
                    sleep(0.5)
            if count == 4:
                raise except_orm('MongoDB connection error', ar_e)
        except Exception as e:
            raise except_orm('MongoDB connection error', e)

        return collection

    def get_db(self):

        try:
            db = self.connection[tools.config['mongodb_name']]
        except AutoReconnect:

            max_tries = 5
            count = 0
            while count < max_tries:
                try:
                    logger.notifyChannel('MongoDB', netsvc.LOG_WARNING,
                                 'WARNING: MongoDB trying to reconnect...')
                    con = self.mongo_connect()

                    db = con[tools.config['mongodb_name']]
                    break
                except AutoReconnect:
                    count += 1
                    sleep(0.5)
        except Exception as e:
            raise except_orm('MongoDB connection error', e)

        return db

    def end_request(self):
        return self.connection.end_request()

mdbpool = MDBConn()
