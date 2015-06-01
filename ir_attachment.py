from osv import osv, fields
from mongodb_backend.osv_mongodb import osv_mongodb


def check_use_objectid(pool, obj_str):
    return isinstance(pool.get(obj_str), osv_mongodb)


class IrAttachemnt(osv.osv):
    _name = 'ir.attachment'
    _inherit = 'ir.attachment'

    def search(self, cr, user, args, offset=0, limit=None, order=None,
            context=None, count=False):
        # [['res_model', '=', 'giscedata.sips.ps'], ['res_id', '=', '556bfea9e838b75c51d1f14c']]
        use_objectid = False
        newargs = []
        for search in args:
            if len(search) != 3:
                newargs.append(search)
                continue
            k, op, value = search
            if k == 'res_model':
                if check_use_objectid(self.pool, value):
                    use_objectid = True
            if k == 'res_id' and use_objectid:
                k = 'res_objectid'
            newargs.append([k, op, value])
        return super(IrAttachemnt, self).search(cr, user, newargs, offset,
                                                limit, order, context, count)

    def create(self, cr, user, vals, context=None):
        # {'lang': 'es_ES', 'tz': False, 'default_res_model': 'giscedata.sips.ps', 'active_ids': [], 'default_res_id': '556bfea9e838b75c51d1f14c', 'active_id': False}
        if context is None:
            context = {}
        use_objectid = False
        for k, v in context.iteritems():
            if k == 'default_res_model':
                if check_use_objectid(self.pool, v):
                    use_objectid = True
                    break
        if use_objectid and 'default_res_id' in context:
            context['default_res_objectid'] = context['default_res_id']
            del context['default_res_id']

        return super(IrAttachemnt, self).create(cr, user, vals, context)

    _columns = {
        'res_objectid': fields.char('Ref ObjectId', size=24)
    }

IrAttachemnt()
