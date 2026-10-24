# -*- coding: utf-8 -*-
"""Enterprise exit: uninstall the Odoo Enterprise modules.

Odoo shell script (not a module). On Odoo.sh, in the shell of the branch:

    odoo-bin shell --no-http
    exec(open('/home/odoo/src/user/tools/ee_exit/ee_uninstall.py').read())

    ee_preflight(env)
        Read-only gate before the uninstall: the build migrated our modules,
        and what we keep from Enterprise is in our own fields and modules
        (RDV type / status / answers, RDV type commercials, SSS projects,
        commission plans, Documents copied to DMS); lists the Studio fields,
        models and actions that go with Studio. ✅ / ⚠️ / ❌ per line.

    ee_final_check(env)
        Read-only gate before the dump: no Enterprise module or leftover,
        the Community modules installed, app icons, view types, users who
        can log in, booking set up, counts still those before the uninstall.

    ee_check(env)
        Read-only. What the uninstall would remove: the modules (in batches),
        the non-Enterprise modules that would go with them, the records the
        modules created that Odoo would delete (and which of them are still
        in use, so kept), the selection values that disappear, and the counts
        of what must survive. Changes nothing.

    ee_uninstall(env, confirm='<database name>')
        On a rehearsal copy (or at go-live). Refused on a database that is
        not neutralized (production) unless go_live=True.
        1. Saves the counts of what must survive (once, in
           ~/ee_exit/<database>/counts_before.json) and the WhatsApp
           account and template definitions (whatsapp.json, without the
           secret tokens).
        2. Archives the automation rules whose only actions send WhatsApp.
        3. Protects the records the Enterprise modules created that are still
           used (e.g. a project with tasks, a stage, an activity type): Odoo
           keeps a record that another module also owns, so they get an
           "__export__" external id.
        4. Uninstalls batch by batch, each with a fresh Odoo registry and
           committed. Can be run again: it continues where it stopped.
        5. Compares the counts with the ones saved before: ✅ / ❌.

Both take keep=('knowledge',) to leave modules (and the Enterprise modules
they need) installed.
"""

import ast
import collections
import contextlib
import json
import os
import re
import time

from odoo import api
from odoo.exceptions import UserError
from odoo.modules.registry import Registry
from odoo.tools import mute_logger

# Not under an Enterprise licence, but go with Enterprise: the bridge of
# bgg_custom_dev, the one-off Documents conversion, the Studio customizations
# and Enterprise add-ons.
EE_EXIT_EXTRA_MODULES = ('bgg_custom_dev_ee', 'bgg_documents_dms', 'studio_customization',
                         # Enterprise add-ons without the Enterprise licence key
                         'ai_fields', 'ai_server_actions', 'web_studio_ai_fields',
                         'spreadsheet_dashboard_marketing_automation')

# Uninstall order. Each batch takes the modules depending on it with it;
# the Enterprise modules in no batch go in a last one.
EE_EXIT_BATCHES = [
    ('Marketing, social, WhatsApp, AI', [
        'marketing_automation', 'social', 'whatsapp', 'ai', 'product_barcodelookup', 'iap_extract']),
    ('Spreadsheets', ['spreadsheet_edition', 'spreadsheet_dashboard_edition']),
    ('Documents', ['bgg_documents_dms', 'documents']),
    ('Appointments', ['bgg_custom_dev_ee', 'appointment']),
    ('Field Service', ['industry_fsm', 'worksheet']),
    ('Accounting', [
        'accountant', 'account_accountant', 'account_reports', 'account_asset', 'account_loans',
        'account_online_synchronization', 'account_followup', 'account_invoice_extract',
        'account_bank_statement_extract', 'account_bank_statement_import', 'account_base_import',
        'account_fiscal_categories', 'account_transfer', 'analytic_enterprise', 'currency_rate_live',
        'l10n_be_coda', 'l10n_be_soda', 'l10n_be_fiscal_categories', 'hr_expense_extract',
        'hr_expense_predict_product']),
    ('Knowledge', ['knowledge']),
    ('Planning, timesheets, commissions, views', [
        'project_enterprise', 'timesheet_grid', 'timer', 'sale_commission', 'hr_recruitment_extract',
        'hr_recruitment_reports', 'crm_enterprise', 'sale_enterprise', 'contacts_enterprise',
        'digest_enterprise', 'mail_enterprise', 'mail_mobile', 'hr_mobile', 'web_mobile',
        'web_gantt', 'web_grid', 'web_cohort', 'web_map']),
    ('Studio', ['studio_customization', 'web_studio']),
    ('Enterprise base', ['website_enterprise', 'web_enterprise']),
]

# What must survive: (label, table, condition). Counted in SQL, archived
# records included.
EE_EXIT_SURVIVAL = [
    ('Contacts', 'res_partner', None),
    ('Users', 'res_users', None),
    ('Internal users (active)', 'res_users', 'active AND NOT share'),
    ('Employees', 'hr_employee', None),
    ('Leads / opportunities', 'crm_lead', None),
    ('Sale orders', 'sale_order', None),
    ('Sale order lines', 'sale_order_line', None),
    ('Invoices / journal entries', 'account_move', None),
    ('Journal items', 'account_move_line', None),
    ('Payments', 'account_payment', None),
    ('Bank statement lines', 'account_bank_statement_line', None),
    ('Taxes', 'account_tax', None),
    ('Calendar events', 'calendar_event', None),
    ('RDVs with an RDV type', 'calendar_event', 'x_rdv_type_id IS NOT NULL'),
    ('RDVs with answers', 'calendar_event', 'x_rdv_answers IS NOT NULL'),
    ('RDV types', 'bgg_rdv_type', None),
    ('Projects', 'project_project', None),
    ('SSS projects', 'project_project', 'x_is_sss_project'),
    ('SSS projects linked to an order', 'project_project', 'x_sss_sale_order_id IS NOT NULL'),
    ('Projects with a DMS folder', 'project_project', 'x_dms_directory_id IS NOT NULL'),
    ('Tasks', 'project_task', None),
    ('Task stages in use', 'project_task_type', 'id IN (SELECT stage_id FROM project_task)'),
    ('Timesheet / analytic lines', 'account_analytic_line', None),
    ('Products', 'product_template', None),
    ('DMS folders', 'dms_directory', None),
    ('DMS files', 'dms_file', None),
    ('DMS file contents', 'ir_attachment', "res_model = 'dms.file'"),
    ('Commissions (BelGoGreen)', 'sale_commission', None),
    ('Commission plans (BelGoGreen)', 'bgg_commission_plan', None),
    ('Applicants', 'hr_applicant', None),
    ('Expenses', 'hr_expense', None),
    ('Messages on orders, leads, projects, tasks, contacts, invoices, events, DMS', 'mail_message',
     "model IN ('sale.order', 'crm.lead', 'project.project', 'project.task', 'res.partner', 'account.move',"
     " 'calendar.event', 'dms.file', 'dms.directory')"),
    ('Automation rules', 'base_automation', None),
]

# Rows linked to a model that is removed are deleted with it (ON DELETE
# CASCADE on the model). These are kept: the link to the removed model is
# emptied first. {table: (link column, other columns emptied with it)}
EE_EXIT_KEEP_LINKED = {
    'calendar_event': ('res_model_id', ('res_id', 'res_model')),
}

# Enterprise fields replaced by bgg_custom_dev's own (same values, same
# ids: bgg.rdv.type kept the appointment.type ids). Conditions of access
# rules, filters, menus and automation rules using them are renamed.
EE_EXIT_FIELD_RENAMES = {
    'calendar.event': {'appointment_type_id': 'x_rdv_type_id', 'appointment_status': 'x_rdv_status'},
    'project.project': {'is_fsm': 'x_is_sss_project'},
}

# Records of these models are not detailed (menus, views, actions, rights...).
EE_EXIT_TECHNICAL = ('res.groups', 'res.groups.privilege', 'report.paperformat', 'digest.tip', 'web_tour.tour',
                     'onboarding.onboarding', 'onboarding.onboarding.step', 'mail.template', 'sms.template',
                     'spreadsheet.dashboard', 'spreadsheet.dashboard.group')
EE_EXIT_META = ('ir.model', 'ir.model.fields', 'ir.model.fields.selection', 'ir.model.constraint',
                'ir.model.relation')


def _ee_print(*args):
    print(*args, flush=True)


@contextlib.contextmanager
def _ee_env(dbname):
    """A fresh environment on the current registry (it changes after each
    uninstall), committed at the end."""
    with Registry(dbname).cursor() as cr:
        yield api.Environment(cr, api.SUPERUSER_ID, {})


def _ee_folder(dbname):
    folder = os.path.join(os.path.expanduser('~'), 'ee_exit', dbname)
    os.makedirs(folder, exist_ok=True)
    return folder


def _ee_module_names(env, keep=()):
    """Installed Enterprise modules (and the extra ones), minus `keep` and the
    Enterprise modules `keep` needs."""
    env.cr.execute("""SELECT name FROM ir_module_module
                       WHERE state IN ('installed', 'to upgrade')
                         AND (license LIKE 'OEEL%%' OR name = ANY(%s))""", [list(EE_EXIT_EXTRA_MODULES)])
    names = {name for (name,) in env.cr.fetchall()}
    if keep:
        Module = env['ir.module.module']
        kept = Module.search([('name', 'in', list(keep))])
        kept |= kept.upstream_dependencies(exclude_states=('uninstalled', 'uninstallable', 'to remove'))
        names -= set(kept.mapped('name'))
    return sorted(names)


def _ee_owned_only(env, names):
    """{model: [res_id]} of the records whose external ids all belong to the
    modules `names` (Odoo deletes those at uninstall)."""
    env.cr.execute("""
        SELECT model, res_id FROM ir_model_data
         GROUP BY model, res_id
        HAVING bool_and(module = ANY(%(names)s) OR module = '__cloc_exclude__')
           AND bool_or(module = ANY(%(names)s))
    """, {'names': list(names)})
    owned = collections.defaultdict(list)
    for model, res_id in env.cr.fetchall():
        owned[model].append(res_id)
    return owned


def _ee_count(env, table, condition=None):
    env.cr.execute("SELECT to_regclass(%s)", ['"%s"' % table])
    if not env.cr.fetchone()[0]:
        return None
    try:
        with env.cr.savepoint(), mute_logger('odoo.sql_db'):
            env.cr.execute('SELECT count(*) FROM "%s"%s' % (table, ' WHERE %s' % condition if condition else ''))
            return env.cr.fetchone()[0]
    except Exception:  # noqa: BLE001 - table or column not there
        return None


def _ee_survival_counts(env):
    return {label: _ee_count(env, table, condition) for label, table, condition in EE_EXIT_SURVIVAL}


def _ee_expected_losses(env, analysis):
    """{survival label: rows expected to go}: the unused records the modules
    created (e.g. an empty "Field Service" project) and their messages."""
    unused = [(model, info['records'] - info['used']) for model, info in analysis['records'].items()
              if not info['technical']]
    unused = [(model, recs) for model, recs in unused if recs]
    losses = {}
    for label, table, condition in EE_EXIT_SURVIVAL:
        loss = 0
        for model, recs in unused:
            ids = env.cr.mogrify('%s', [tuple(recs.ids)]).decode()
            if table == env[model]._table:
                loss += _ee_count(env, table, '%sid IN %s' % ('(%s) AND ' % condition if condition else '', ids)) or 0
            elif table == 'mail_message':
                loss += _ee_count(env, table, '(%s) AND model = %s AND res_id IN %s' % (
                    condition or 'TRUE', env.cr.mogrify('%s', [model]).decode(), ids)) or 0
        for link_table, column, deltype, __ in analysis['model_links']:
            if link_table == table and deltype == 'c' and table not in EE_EXIT_KEEP_LINKED:
                ids = env.cr.mogrify('%s', [tuple(analysis['dropped_model_ids'])]).decode()
                loss += _ee_count(env, table, '%s"%s" IN %s' % ('(%s) AND ' % condition if condition else '',
                                                               column, ids)) or 0
        losses[label] = loss
    return losses


def _ee_analyse(env, names):
    """What Odoo would delete with the modules `names`."""
    owned = _ee_owned_only(env, names)
    env.cr.execute("SELECT id, model FROM ir_model WHERE id = ANY(%s)", [owned.get('ir.model', [])])
    dropped_models = {model for __, model in env.cr.fetchall()}
    dropped_tables = {env[m]._table for m in dropped_models if m in env and env[m]._auto and not env[m]._abstract}
    env.cr.execute("SELECT id, model, name FROM ir_model_fields WHERE id = ANY(%s)", [owned.get('ir.model.fields', [])])
    dropped_fields = {(model, name) for __, model, name in env.cr.fetchall()}

    records = {}
    for model, ids in sorted(owned.items()):
        if model in EE_EXIT_META or model in dropped_models or model not in env:
            continue
        Model = env[model].with_context(active_test=False)
        recs = Model.browse(ids).exists()
        if recs:
            technical = model.startswith('ir.') or model in EE_EXIT_TECHNICAL or not Model._auto
            records[model] = {'records': recs, 'technical': technical, 'used': recs.browse(), 'refs': []}

    def foreign_keys(sql, table):
        env.cr.execute("""
            SELECT cl.relname, a.attname, cf.relname, c.confdeltype
              FROM pg_constraint c
              JOIN pg_class cl ON cl.oid = c.conrelid
              JOIN pg_class cf ON cf.oid = c.confrelid
              JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1]
             WHERE c.contype = 'f' AND %s = %%s::regclass""" % sql, [table])
        return env.cr.fetchall()

    has_id_cache, fk_cache = {}, {}

    def has_id(table):
        if table not in has_id_cache:
            env.cr.execute("SELECT 1 FROM pg_attribute WHERE attrelid = %s::regclass AND attname = 'id'",
                           ['"%s"' % table])
            has_id_cache[table] = bool(env.cr.fetchone())
        return has_id_cache[table]

    def referencing(table):
        """Foreign keys pointing to `table` from tables that stay."""
        if table not in fk_cache:
            fk_cache[table] = [fk for fk in foreign_keys('c.confrelid', table)
                               if fk[0] not in dropped_tables and not fk[0].startswith('ir_')]
        return fk_cache[table]

    def doomed():
        """{table: ids} deleted: the records not kept, and the rows deleted
        with them (ON DELETE CASCADE, e.g. the lines of a report), and so on."""
        dies = collections.defaultdict(set)
        todo = []
        for model, info in records.items():
            table = env[model]._table
            ids = set(info['records'].ids) - set(info['used'].ids)
            dies[table] |= ids
            todo.append((table, ids))
        while todo:
            table, ids = todo.pop()
            for child, column, __, deltype in referencing(table):
                if deltype != 'c' or not has_id(child):
                    continue
                env.cr.execute('SELECT id FROM "%s" WHERE "%s" = ANY(%%s)' % (child, column), [list(ids)])
                new = {r[0] for r in env.cr.fetchall()} - dies[child]
                if new:
                    dies[child] |= new
                    todo.append((child, new))
        return dies

    # A record is kept when a row that stays points to it and would be
    # emptied (set null) or would block the deletion (restrict). Rows deleted
    # with it (cascade) are not a use. Repeated, as a kept record keeps the
    # rows below it.
    for __ in range(10):
        dies = doomed()
        changed = False
        for model, info in records.items():
            if info['technical']:
                continue
            used, refs = set(), []
            for table, column, __, deltype in referencing(env[model]._table):
                if deltype == 'c':
                    continue
                where, params = ['"%s" = ANY(%%s)' % column], [info['records'].ids]
                if has_id(table):
                    where.append('NOT (id = ANY(%s))')
                    params.append(list(dies.get(table, ())))
                else:
                    # many2many link: the other side must stay
                    others = [(c, t) for __, c, t, __ in foreign_keys('c.conrelid', table) if c != column]
                    if any(t in dropped_tables for __, t in others):
                        continue
                    for other_column, other_table in others:
                        where.append('NOT ("%s" = ANY(%%s))' % other_column)
                        params.append(list(dies.get(other_table, ())))
                env.cr.execute('SELECT "%s", count(*) FROM "%s" WHERE %s GROUP BY 1'
                               % (column, table, ' AND '.join(where)), params)
                rows = env.cr.fetchall()
                if rows:
                    used.update(r[0] for r in rows)
                    action = {'n': 'emptied', 'r': 'blocks', 'a': 'blocks'}.get(deltype, deltype)
                    refs.append('%s.%s: %s rows (%s)' % (table, column, sum(r[1] for r in rows), action))
            if used != set(info['used'].ids):
                changed = True
            info['used'], info['refs'] = info['records'].browse(sorted(used)), refs
        if not changed:
            break

    selections = []
    env.cr.execute("""SELECT f.model, f.name, s.value FROM ir_model_fields_selection s
                        JOIN ir_model_fields f ON f.id = s.field_id WHERE s.id = ANY(%s)""",
                   [owned.get('ir.model.fields.selection', [])])
    for model, name, value in env.cr.fetchall():
        if model in dropped_models or (model, name) in dropped_fields or model not in env:
            continue
        field = env[model]._fields.get(name)
        if not field or not field.store or not env[model]._auto:
            continue
        count = _ee_count(env, env[model]._table, '"%s" = %s' % (name, env.cr.mogrify('%s', [value]).decode()))
        if count:
            ondelete = getattr(field, 'ondelete', None)
            ondelete = ondelete.get(value) if isinstance(ondelete, dict) else None
            selections.append((model, name, value, count, ondelete))
    # rows of kept tables linked to a removed model (e.g. a calendar event
    # linked to an appointment, an automation rule on an Enterprise model)
    env.cr.execute("SELECT id FROM ir_model WHERE id = ANY(%s)", [owned.get('ir.model', [])])
    dropped_model_ids = [r[0] for r in env.cr.fetchall()]
    model_links = []
    for table, column, __, deltype in foreign_keys('c.confrelid', 'ir_model'):
        if table in dropped_tables or table.startswith('ir_') or not has_id(table):
            continue
        env.cr.execute('SELECT count(*) FROM "%s" WHERE "%s" = ANY(%%s)' % (table, column), [dropped_model_ids])
        count = env.cr.fetchone()[0]
        if count:
            model_links.append((table, column, deltype, count))
    return {'dropped_models': dropped_models, 'dropped_fields': dropped_fields, 'records': records,
            'selections': selections, 'dropped_model_ids': dropped_model_ids, 'model_links': model_links}


def _ee_drop_orphans(env):
    """External ids pointing to model, field or selection definitions that no
    longer exist (e.g. a Studio field of a model an earlier batch removed):
    Odoo's uninstall reads them and stops ("Record does not exist")."""
    removed = 0
    for model, table in (('ir.model.fields', 'ir_model_fields'), ('ir.model', 'ir_model'),
                         ('ir.model.fields.selection', 'ir_model_fields_selection'),
                         ('ir.model.constraint', 'ir_model_constraint')):
        env.cr.execute("""DELETE FROM ir_model_data d WHERE d.model = %%s
                           AND NOT EXISTS (SELECT 1 FROM "%s" t WHERE t.id = d.res_id)""" % table, [model])
        removed += env.cr.rowcount
    if removed:
        _ee_print("    removed %s external ids pointing to nothing" % removed)
    return removed


def _ee_keep_user_rights(env, analysis):
    """Keep the rights users get through a group the uninstall deletes.

    In Odoo 19 most users are "Internal User" (and Sales, Project...) through
    another group, e.g. "Appointments: User": when that group is deleted,
    the rights it implied go with it and the user becomes a portal-like
    user. Those rights are given directly to the user first."""
    deleted = set(analysis['records']['res.groups']['records'].ids) if 'res.groups' in analysis['records'] else set()
    if not deleted:
        return 0
    Groups = env['res.groups'].with_context(active_test=False)
    implied = {}

    def reach(group_ids):
        seen, todo = set(), [g for g in group_ids if g not in deleted]
        while todo:
            gid = todo.pop()
            if gid in seen:
                continue
            seen.add(gid)
            if gid not in implied:
                implied[gid] = Groups.browse(gid).implied_ids.ids
            todo.extend(g for g in implied[gid] if g not in deleted)
        return seen

    changed = 0
    for user in env['res.users'].with_context(active_test=False).search([]):
        explicit = set(user.group_ids.ids) - deleted
        missing = set(user.all_group_ids.ids) - deleted - reach(explicit)
        added = []
        while missing:
            # the group giving the most of what is missing first (e.g. Internal User)
            best = max(sorted(missing), key=lambda g: len(reach([g]) & missing))
            added.append(best)
            explicit.add(best)
            missing -= reach(explicit)
        if added:
            user.write({'group_ids': [(4, gid) for gid in added]})
            changed += 1
    _ee_print("Kept the rights of %s users that came through deleted groups" % changed)
    return changed


def _ee_domain_paths(domain):
    """Field paths of the conditions of a stored domain: the first item of
    each (path, operator, value) of the domain list (values are not
    looked at). [] when the text is not a plain domain list."""
    try:
        node = ast.parse(domain.strip(), mode='eval').body
    except SyntaxError:
        return []
    if not isinstance(node, (ast.List, ast.Tuple)):
        return []
    return [elt.elts[0].value for elt in node.elts
            if isinstance(elt, (ast.List, ast.Tuple)) and len(elt.elts) == 3
            and isinstance(elt.elts[0], ast.Constant) and isinstance(elt.elts[0].value, str)]


def _ee_domains(env):
    """(label, record, field name, model, domain text) of the conditions
    stored in the database: access rules, filters, menus, automation rules."""
    rows = []
    for Model, fname, model_of in (
            ('ir.rule', 'domain_force', lambda r: r.model_id.model),
            ('ir.filters', 'domain', lambda r: r.model_id),
            ('ir.actions.act_window', 'domain', lambda r: r.res_model),
            ('base.automation', 'filter_domain', lambda r: r.model_id.model),
            ('base.automation', 'filter_pre_domain', lambda r: r.model_id.model)):
        if Model not in env or fname not in env[Model]._fields:
            continue
        for rec in env[Model].with_context(active_test=False).search([(fname, '!=', False)]):
            rows.append((Model, rec, fname, model_of(rec), rec[fname]))
    return rows


def _ee_fix_domains(env, dropped_fields=None, dry_run=False):
    """Rename the replaced Enterprise fields in stored conditions, and list
    the conditions still using a field that is (or will be) removed.
    dropped_fields: {(model, field)} before the uninstall; None after it
    (then a field missing from the model is reported)."""
    renamed, broken = [], []
    for Model, rec, fname, model, domain in _ee_domains(env):
        renames = EE_EXIT_FIELD_RENAMES.get(model, {})
        new = domain
        for old_name in {p.split('.')[0] for p in _ee_domain_paths(domain)} & set(renames):
            new = re.sub(r"""(['"])%s(?=['".])""" % re.escape(old_name), r'\g<1>' + renames[old_name], new)
        if new != domain:
            if not dry_run:
                try:
                    with env.cr.savepoint():
                        rec.write({fname: new})
                except Exception:  # noqa: BLE001 - still invalid (another removed field): written as is
                    env.cr.execute('UPDATE "%s" SET "%s" = %%s WHERE id = %%s' % (rec._table, fname), [new, rec.id])
                    rec.invalidate_recordset([fname])
            renamed.append('%s %s %r' % (Model, rec.id, rec.display_name))
        if model not in env:
            continue
        for path in _ee_domain_paths(new):
            first = path.split('.')[0]
            gone = ((model, first) in dropped_fields if dropped_fields is not None
                    else first not in env[model]._fields)
            if gone:
                broken.append('%s %s %r on %s: %s' % (Model, rec.id, rec.display_name, model, first))
    _ee_print("    conditions %s to our fields: %s" % ('to rename' if dry_run else 'renamed', ', '.join(renamed) or 'none'))
    _ee_print("    conditions still using a removed field: %s" % ('; '.join(broken) or 'none ✅'))
    return renamed, broken


def _ee_batches(names):
    names = set(names)
    batches, placed = [], set()
    for label, batch in EE_EXIT_BATCHES:
        batch = [n for n in batch if n in names]
        if batch:
            batches.append((label, batch))
            placed.update(batch)
    if names - placed:
        batches.append(('Other Enterprise modules', sorted(names - placed)))
    return batches


def ee_check(env, keep=()):
    """Read-only report of what the uninstall would do."""
    names = _ee_module_names(env, keep)
    Module = env['ir.module.module']
    modules = Module.search([('name', 'in', names)])
    also = modules.downstream_dependencies() - modules
    _ee_print("=== %s Enterprise modules to uninstall%s" % (len(names), ' (kept: %s)' % ', '.join(keep) if keep else ''))
    for label, batch in _ee_batches(names):
        _ee_print("  %-45s %s" % (label, ', '.join(batch)))
    _ee_print("\n=== OTHER MODULES THAT WOULD GO WITH THEM")
    _ee_print("  " + (', '.join(sorted(also.mapped('name'))) or 'none ✅'))

    analysis = _ee_analyse(env, names)
    _ee_print("\n=== %s Enterprise tables dropped, %s Enterprise fields removed from kept models"
              % (len(analysis['dropped_models']), len(analysis['dropped_fields'])))

    _ee_print("\n=== RECORDS THE MODULES CREATED, DELETED WITH THEM (business data)")
    for model, info in analysis['records'].items():
        if info['technical']:
            continue
        recs, used = info['records'], info['used']
        unused = recs - used
        _ee_print("  %s: %s" % (model, len(recs)))
        if used:
            _ee_print("     KEPT, still in use (%s): %s" % (len(used), used.mapped('display_name')[:12]))
            for ref in info['refs']:
                _ee_print("        - %s" % ref)
        if unused:
            _ee_print("     deleted, unused (%s): %s" % (len(unused), unused.mapped('display_name')[:12]))
    _ee_print("\n=== TECHNICAL RECORDS DELETED (menus, views, actions, rights, groups...)")
    _ee_print("  " + ', '.join('%s %s' % (model, len(info['records']))
                              for model, info in analysis['records'].items() if info['technical']))

    _ee_print("\n=== ROWS LINKED TO A REMOVED MODEL")
    for table, column, deltype, count in analysis['model_links']:
        fate = ('KEPT, link emptied first' if table in EE_EXIT_KEEP_LINKED else
                {'c': 'deleted with the model', 'n': 'link emptied', 'r': 'blocks', 'a': 'blocks'}.get(deltype, deltype))
        _ee_print("  %s.%s: %s rows (%s)" % (table, column, count, fate))
    if not analysis['model_links']:
        _ee_print("  none ✅")

    _ee_print("\n=== CONDITIONS (ACCESS RULES, FILTERS, MENUS, AUTOMATIONS) ON REMOVED FIELDS")
    _ee_fix_domains(env, analysis['dropped_fields'], dry_run=True)

    _ee_print("\n=== VALUES THAT DISAPPEAR FROM KEPT FIELDS")
    for model, name, value, count, ondelete in analysis['selections']:
        _ee_print("  %s.%s = %r: %s records%s" % (model, name, value, count, ' (on removal: %s)' % ondelete if ondelete else ''))
    if not analysis['selections']:
        _ee_print("  none ✅")

    _ee_print("\n=== NOT MOVED YET")
    if 'knowledge' in names:
        _ee_print("  Knowledge: %s articles would be lost (move them first, or keep=('knowledge',))"
                  % _ee_count(env, 'knowledge_article'))
    if 'whatsapp' in names:
        rules = _ee_whatsapp_rules(env)
        _ee_print("  WhatsApp: %s active automation rules send WhatsApp: %s" % (len(rules), rules.mapped('name')))
        _ee_print("            (ee_uninstall archives them and saves the templates)")

    _ee_print("\n=== WHAT MUST SURVIVE (now, and what goes on purpose: the unused records above)")
    losses = _ee_expected_losses(env, analysis)
    for label, count in _ee_survival_counts(env).items():
        _ee_print("  %-75s %s%s" % (label, '-' if count is None else count,
                                     '   (-%s expected)' % losses[label] if losses.get(label) else ''))
    env.cr.rollback()


def _ee_whatsapp_rules(env):
    """Active automation rules whose only actions send WhatsApp."""
    return env['base.automation'].search([]).filtered(
        lambda r: r.action_server_ids and all(a.state == 'whatsapp' for a in r.action_server_ids))


def ee_export_whatsapp(env):
    """WhatsApp accounts and templates to a JSON file (secret tokens left
    out), to set WhatsApp up again on Community."""
    if 'whatsapp.template' not in env:
        return None

    def plain(records):
        rows = []
        for rec in records:
            vals = {}
            for name, field in rec._fields.items():
                if (not field.store or field.type in ('binary', 'one2many', 'many2many')
                        or 'token' in name or 'secret' in name):
                    continue
                value = rec[name]
                if field.type == 'many2one':
                    value = value.display_name if value else False
                vals[name] = value
            rows.append(vals)
        return rows

    templates = env['whatsapp.template'].with_context(active_test=False).search([])
    data = {
        'accounts': plain(env['whatsapp.account'].with_context(active_test=False).search([])),
        'templates': [dict(vals, variables=plain(t.variable_ids), buttons=plain(t.button_ids))
                      for t, vals in zip(templates, plain(templates))],
    }
    path = os.path.join(_ee_folder(env.cr.dbname), 'whatsapp.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    _ee_print("WhatsApp: %s accounts, %s templates saved to %s" % (len(data['accounts']), len(templates), path))
    return path


def ee_uninstall(env, confirm=None, keep=(), go_live=False):
    dbname = env.cr.dbname
    if confirm != dbname:
        raise UserError("Give the database name to confirm: ee_uninstall(env, confirm=%r)" % dbname)
    neutralized = env['ir.config_parameter'].sudo().get_param('database.is_neutralized')
    if not neutralized and not go_live:
        raise UserError("This database is not neutralized (production?). Use go_live=True only at go-live.")
    env.cr.rollback()   # release what the shell read: the uninstall drops tables
    folder = _ee_folder(dbname)
    before_path = os.path.join(folder, 'counts_before.json')

    # 1-3: counts, WhatsApp, protection
    with _ee_env(dbname) as env:
        names = _ee_module_names(env, keep)
        modules = env['ir.module.module'].search([('name', 'in', names)])
        also = modules.downstream_dependencies() - modules
        if also:
            raise UserError("Non-Enterprise modules would go too: %s. Stopped." % also.mapped('name'))
        if not os.path.exists(before_path):
            with open(before_path, 'w', encoding='utf-8') as f:
                json.dump(_ee_survival_counts(env), f, ensure_ascii=False, indent=2)
            _ee_print("Counts saved to %s" % before_path)
        if 'whatsapp' in names:
            ee_export_whatsapp(env)
            rules = _ee_whatsapp_rules(env)
            rules.active = False
            _ee_print("Archived %s WhatsApp automation rules: %s" % (len(rules), rules.mapped('name')))
        analysis = _ee_analyse(env, names)
        for table, (column, others) in EE_EXIT_KEEP_LINKED.items():
            if not analysis['dropped_model_ids'] or _ee_count(env, table) is None:
                continue
            env.cr.execute('UPDATE "%s" SET %s WHERE "%s" = ANY(%%s)' % (
                table, ', '.join('"%s" = NULL' % c for c in (column,) + tuple(others)), column),
                [analysis['dropped_model_ids']])
            if env.cr.rowcount:
                _ee_print("Kept %s %s rows linked to a removed model (link emptied)" % (env.cr.rowcount, table))
        losses_path = os.path.join(folder, 'expected_losses.json')
        if not os.path.exists(losses_path):
            with open(losses_path, 'w', encoding='utf-8') as f:
                json.dump(_ee_expected_losses(env, analysis), f, ensure_ascii=False, indent=2)
        _ee_keep_user_rights(env, analysis)
        _ee_fix_domains(env, analysis['dropped_fields'])
        protected = 0
        Data = env['ir.model.data']
        for model, info in analysis['records'].items():
            for rec in info['used']:
                name = 'ee_exit_%s_%s' % (model.replace('.', '_'), rec.id)
                if not Data.search_count([('module', '=', '__export__'), ('name', '=', name)]):
                    Data.create({'module': '__export__', 'name': name, 'model': model, 'res_id': rec.id,
                                 'noupdate': True})
                    protected += 1
        _ee_print("Protected %s records still in use" % protected)

    # 4: batches
    for label, batch in _ee_batches(names):
        for attempt in range(5):
            try:
                with _ee_env(dbname) as env:
                    todo = env['ir.module.module'].search([('name', 'in', batch), ('state', '=', 'installed')])
                    if not todo:
                        break
                    start = time.time()
                    _ee_print("\n--- %s: %s" % (label, ', '.join(todo.mapped('name'))))
                    _ee_drop_orphans(env)
                    env.cr.commit()
                    todo.button_immediate_uninstall()
                    _ee_print("    done in %.0f s" % (time.time() - start))
                break
            except UserError as error:
                if 'Odoo is currently processing' not in str(error):
                    raise   # a real error: stop and show it
                _ee_print("    busy (%s), retrying in 30 s" % error)   # a cron or another module operation
                time.sleep(30)
        else:
            raise UserError("Batch %s could not run. Stopped; run ee_uninstall again later." % label)

    # 5: retry what a lock kept Odoo from removing, then compare
    _ee_cleanup(dbname)
    with _ee_env(dbname) as env:
        left = _ee_module_names(env, keep)
        with open(before_path, encoding='utf-8') as f:
            before = json.load(f)
        with open(os.path.join(folder, 'expected_losses.json'), encoding='utf-8') as f:
            losses = json.load(f)
        after = _ee_survival_counts(env)
        _ee_print("\n=== WHAT MUST SURVIVE: before -> after")
        ok = True
        for label, count in after.items():
            old, loss = before.get(label), losses.get(label) or 0
            good = old is None or (count is not None and count >= old - loss)
            ok = ok and good
            _ee_print("  %s %-75s %s -> %s%s" % ('✅' if good else '❌', label, old, count,
                                               '   (-%s expected)' % loss if loss else ''))
        with open(os.path.join(folder, 'counts_after.json'), 'w', encoding='utf-8') as f:
            json.dump(after, f, ensure_ascii=False, indent=2)
        _ee_print("\nEnterprise modules still installed: %s" % (', '.join(left) or 'none ✅'))
        _ee_print("All counts kept ✅" if ok else "SOME COUNTS WENT DOWN ❌: check before going further")


def ee_blockers(env):
    """Other connections with a transaction open for more than 30 s: they
    keep the uninstall from dropping columns ("lock timeout")."""
    env.cr.execute("""
        SELECT pid, state, application_name, client_addr,
               date_trunc('second', now() - xact_start), left(regexp_replace(query, '\\s+', ' ', 'g'), 100)
          FROM pg_stat_activity
         WHERE datname = current_database() AND pid != pg_backend_pid()
           AND xact_start < now() - interval '30 seconds'
         ORDER BY xact_start""")
    rows = env.cr.fetchall()
    for row in rows:
        _ee_print("  pid %s  %-20s %-15s %-15s open for %s  %s" % row)
    if not rows:
        _ee_print("  none ✅")
    env.cr.rollback()
    return rows


def ee_cleanup(env, lock_wait='60s'):
    """Retry removing what the uninstalled Enterprise modules left (columns,
    indexes, fields a lock kept Odoo from dropping), and let go of NOT NULL
    on columns no field uses any more (they would block new records)."""
    env.cr.rollback()
    _ee_cleanup(env.cr.dbname, lock_wait)


def _ee_cleanup(dbname, lock_wait='60s'):
    with _ee_env(dbname) as env:
        env.cr.execute("SET lock_timeout = %s", [lock_wait])
        _ee_drop_orphans(env)
        env.cr.execute("""
            SELECT d.module, d.model, count(*) FROM ir_model_data d
              JOIN ir_module_module m ON m.name = d.module
             WHERE m.state = 'uninstalled' AND (m.license LIKE 'OEEL%%' OR m.name = ANY(%s))
             GROUP BY 1, 2 ORDER BY 1, 2""", [list(EE_EXIT_EXTRA_MODULES)])
        left = env.cr.fetchall()
        _ee_print("\n=== LEFT BY THE UNINSTALLED MODULES: %s"
                  % (', '.join('%s %s %s' % row for row in left) or 'nothing ✅'))
        if left:
            env['ir.model.data']._module_data_uninstall(sorted({row[0] for row in left}))
            env.cr.execute("""
                SELECT count(*) FROM ir_model_data d JOIN ir_module_module m ON m.name = d.module
                 WHERE m.state = 'uninstalled' AND (m.license LIKE 'OEEL%%' OR m.name = ANY(%s))""",
                           [list(EE_EXIT_EXTRA_MODULES)])
            _ee_print("    after retry: %s left" % env.cr.fetchone()[0])

        # columns without a field that still require a value
        fixed = []
        for model in env.registry.values():
            if model._abstract or not model._auto or model._table_query:
                continue
            stored = {name for name, field in model._fields.items() if field.store and field.column_type}
            env.cr.execute("""
                SELECT column_name FROM information_schema.columns
                 WHERE table_schema = 'public' AND table_name = %s AND is_nullable = 'NO' AND column_default IS NULL""",
                           [model._table])
            for (column,) in env.cr.fetchall():
                if column not in stored and column != 'id':
                    env.cr.execute('ALTER TABLE "%s" ALTER COLUMN "%s" DROP NOT NULL' % (model._table, column))
                    fixed.append('%s.%s' % (model._table, column))
        _ee_print("    leftover required columns made optional: %s" % (', '.join(fixed) or 'none ✅'))

        # view types of removed modules (gantt, map, grid, cohort) still
        # listed in window actions: Odoo refuses to open such an action
        valid = {value for value, __ in env['ir.ui.view']._fields['type'].selection}
        env.cr.execute("SELECT id, view_mode FROM ir_act_window WHERE view_mode IS NOT NULL")
        actions = []
        for action_id, view_mode in env.cr.fetchall():
            modes = [m.strip() for m in view_mode.split(',') if m.strip()]
            keep = [m for m in modes if m in valid] or ['list', 'form']
            if keep != modes:
                env.cr.execute("UPDATE ir_act_window SET view_mode = %s WHERE id = %s", [','.join(keep), action_id])
                actions.append('%s (%s -> %s)' % (action_id, view_mode, ','.join(keep)))
        _ee_print("    actions with removed view types fixed: %s" % (', '.join(actions) or 'none ✅'))

        _ee_fix_domains(env)

        # app icons in Studio's format ("icon class,colour,background", drawn
        # by the Enterprise home menu): Community expects "module,path" and
        # the OCA app menu (web_responsive) stops on them. Default icon.
        env.cr.execute("""WITH bad AS (SELECT id, web_icon FROM ir_ui_menu
                                        WHERE array_length(string_to_array(web_icon, ','), 1) <> 2)
                          UPDATE ir_ui_menu m SET web_icon = NULL FROM bad WHERE m.id = bad.id
                       RETURNING m.id, bad.web_icon""")
        menus = env.cr.fetchall()
        env.registry.clear_cache()
        _ee_print("    app icons in Studio's format reset: %s" % (', '.join('%s (%s)' % m for m in menus) or 'none ✅'))
    # the running Odoo workers drop their cached menus and actions
    Registry(dbname).signal_changes()


# ----------------------------------------------------------------------
# Gates: read-only checks before the uninstall and before the dump
# ----------------------------------------------------------------------

# Our modules, moved off Enterprise by their migrations at the build
EE_EXIT_MOVED_MODULES = ('bgg_custom_dev', 'belgogreen_sales_commission')
# Installed before the uninstall (the Documents copy)
EE_EXIT_DMS_MODULES = ('dms', 'bgg_dms', 'bgg_dms_project', 'bgg_documents_dms')
# Installed on the database that is restored on the Community server
EE_EXIT_TARGET_MODULES = ('bgg_custom_dev', 'belgogreen_sales_commission', 'dms', 'bgg_dms', 'bgg_dms_project',
                          'web_responsive', 'resource_booking', 'web_calendar_slot_duration', 'bgg_booking')
# Not taken to the Community server
EE_EXIT_NOT_TAKEN = ('bgg_staging_rebuild',)


def _ee_report(title, rows):
    """Print (status, label, detail) rows; status: ok / bad / warn / na.
    Returns True when no row is bad."""
    marks = {'ok': '✅', 'bad': '❌', 'warn': '⚠️ ', 'na': '– '}
    _ee_print("\n=== %s" % title)
    for status, label, detail in rows:
        _ee_print("  %s %-62s %s" % (marks[status], label, detail if detail is not None else ''))
    return not any(status == 'bad' for status, __, __ in rows)


def _ee_has_column(env, table, column):
    env.cr.execute("SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
                   [table, column])
    return bool(env.cr.fetchone())


def _ee_zero(label, count, total=None, hint=''):
    """A row that is good when `count` is 0 (None: table not there)."""
    if count is None:
        return ('na', label, 'not on this database')
    detail = '%s%s%s' % (count, ' of %s' % total if total is not None else '', '   ' + hint if count and hint else '')
    return ('ok' if not count else 'bad', label, detail)


def _ee_module_rows(env, names, need=True):
    rows = []
    for module in env['ir.module.module'].search([('name', 'in', list(names))], order='name'):
        if module.state != 'installed':
            rows.append(('bad' if need else 'ok', 'Module %s' % module.name, module.state))
        elif module.latest_version != module.installed_version:
            rows.append(('bad', 'Module %s' % module.name, 'installed %s, code %s: update it'
                         % (module.latest_version, module.installed_version)))
        else:
            rows.append(('ok', 'Module %s' % module.name, module.latest_version))
    missing = set(names) - set(env['ir.module.module'].search([('name', 'in', list(names))]).mapped('name'))
    rows += [('bad' if need else 'ok', 'Module %s' % name, 'not in the addons path') for name in sorted(missing)]
    return rows


def _ee_pending_modules(env):
    pending = env['ir.module.module'].search([('state', 'in', ('to install', 'to upgrade', 'to remove'))])
    return ('bad' if pending else 'ok', 'Modules left half-way (to install / upgrade / remove)',
            ', '.join('%s (%s)' % (m.name, m.state) for m in pending) or 'none')


def ee_preflight(env):
    """Read-only. Before the uninstall: is everything the Enterprise apps
    hold that we keep already in our own fields and modules?"""
    ok = True
    Module = env['ir.module.module']
    has_appointment = bool(Module.search_count([('name', '=', 'appointment'), ('state', '=', 'installed')]))

    rows = _ee_module_rows(env, EE_EXIT_MOVED_MODULES) + _ee_module_rows(env, EE_EXIT_DMS_MODULES)
    if has_appointment:
        rows += _ee_module_rows(env, ('bgg_custom_dev_ee',))
    rows.append(_ee_pending_modules(env))
    ok &= _ee_report("MODULES (build done, DMS installed)", rows)

    # RDVs: Appointments -> bgg_custom_dev (migration 19.0.2.0.0 / 19.0.2.2.0, kept in sync by the bridge)
    rows = []
    if _ee_has_column(env, 'calendar_event', 'appointment_type_id'):
        total = _ee_count(env, 'calendar_event', 'appointment_type_id IS NOT NULL')
        rows.append(_ee_zero('RDVs whose RDV type is missing or different',
                             _ee_count(env, 'calendar_event', 'appointment_type_id IS NOT NULL AND '
                                       'x_rdv_type_id IS DISTINCT FROM appointment_type_id'), total))
        rows.append(_ee_zero('RDVs whose RDV status is different',
                             _ee_count(env, 'calendar_event', 'appointment_type_id IS NOT NULL AND '
                                       'x_rdv_status IS DISTINCT FROM appointment_status'), total))
    else:
        rows.append(('na', 'RDV type and status', 'Appointments not on this database'))
    if _ee_count(env, 'appointment_answer_input') is not None:
        answered = _ee_count(env, 'calendar_event', 'id IN (SELECT calendar_event_id FROM appointment_answer_input)')
        rows.append(_ee_zero('RDVs with answers but no questionnaire summary',
                             _ee_count(env, 'calendar_event', 'x_rdv_answers IS NULL AND '
                                       'id IN (SELECT calendar_event_id FROM appointment_answer_input)'), answered))
    if _ee_count(env, 'appointment_type') is not None:
        rows.append(_ee_zero('Appointment types without their RDV type (same id)',
                             _ee_count(env, 'appointment_type', 'id NOT IN (SELECT id FROM bgg_rdv_type)'),
                             _ee_count(env, 'appointment_type')))
        env.cr.execute("""SELECT relation_table, column1, column2 FROM ir_model_fields
                           WHERE model = 'appointment.type' AND name = 'staff_user_ids'""")
        staff = env.cr.fetchone()
        if staff and all(staff) and _ee_count(env, staff[0]) is not None:
            table, type_col, user_col = staff
            rows.append(_ee_zero('Appointment staff missing from the RDV type commercials', _ee_count(
                env, table, 'NOT EXISTS (SELECT 1 FROM bgg_rdv_type_res_users_rel b WHERE b.rdv_type_id = '
                '"%s"."%s" AND b.user_id = "%s"."%s")' % (table, type_col, table, user_col)), _ee_count(env, table)))
    ok &= _ee_report("RDVs (Appointments -> bgg_custom_dev)", rows)

    # SSS projects: Field Service -> bgg_custom_dev
    rows = []
    if _ee_has_column(env, 'project_project', 'is_fsm'):
        rows.append(_ee_zero('Field Service projects not flagged SSS',
                             _ee_count(env, 'project_project', 'is_fsm AND x_is_sss_project IS NOT TRUE'),
                             _ee_count(env, 'project_project', 'is_fsm')))
    else:
        rows.append(('na', 'Field Service projects', 'Field Service not on this database'))
    no_order = _ee_count(env, 'project_project', 'x_is_sss_project AND x_sss_sale_order_id IS NULL')
    rows.append(('na' if no_order is None else 'ok' if not no_order else 'warn', 'SSS projects without their sale order',
                 '%s (open decisions #4: their tasks are not under the order\'s "Tâches")' % no_order
                 if no_order else 'not on this database' if no_order is None else 0))
    ok &= _ee_report("SSS PROJECTS (Field Service -> bgg_custom_dev)", rows)

    # Commission plans: Enterprise sale_commission -> belgogreen_sales_commission
    rows = []
    for table in ('sale_commission', 'hr_commission_role_config', 'bgg_commission_plan_user'):
        if _ee_has_column(env, table, 'plan_id'):
            rows.append(_ee_zero('%s rows on a plan that is not ours' % table, _ee_count(
                env, table, 'plan_id IS NOT NULL AND plan_id NOT IN (SELECT id FROM bgg_commission_plan)'),
                _ee_count(env, table, 'plan_id IS NOT NULL')))
    ok &= _ee_report("COMMISSIONS (sale_commission -> belgogreen_sales_commission)", rows)

    # Documents -> DMS (bgg_documents_dms)
    rows = []
    if _ee_count(env, 'documents_document') is None:
        rows.append(('na', 'Documents', 'Documents not on this database'))
    elif _ee_count(env, 'bgg_documents_dms_map') is None:
        rows.append(('bad', 'Documents copied to DMS', 'never: run step 2 (the copy)'))
    else:
        moved = "id NOT IN (SELECT document_id FROM bgg_documents_dms_map) AND shortcut_document_id IS NULL"
        rows.append(_ee_zero('Folders not copied', _ee_count(env, 'documents_document', "type = 'folder' AND " + moved),
                             _ee_count(env, 'documents_document', "type = 'folder'"), hint='run step 2 again'))
        rows.append(_ee_zero('Files not copied', _ee_count(
            env, 'documents_document', "type = 'binary' AND attachment_id IS NOT NULL AND " + moved + " AND "
            "attachment_id NOT IN (SELECT id FROM ir_attachment WHERE mimetype = 'application/o-spreadsheet')"),
            _ee_count(env, 'documents_document', "type = 'binary' AND attachment_id IS NOT NULL"),
            hint='run step 2 again; still there: see the log of the copy'))
        skipped = _ee_count(env, 'documents_document', "type = 'url' OR shortcut_document_id IS NOT NULL OR "
                            "attachment_id IN (SELECT id FROM ir_attachment WHERE mimetype = 'application/o-spreadsheet')")
        rows.append(('ok', 'Not moved on purpose (links, shortcuts, spreadsheets)', skipped))
        if _ee_has_column(env, 'project_project', 'documents_folder_id'):
            rows.append(_ee_zero('Projects with a Documents folder but no DMS folder', _ee_count(
                env, 'project_project', 'documents_folder_id IS NOT NULL AND x_dms_directory_id IS NULL '
                'AND documents_folder_id IN (SELECT document_id FROM bgg_documents_dms_map)'),
                _ee_count(env, 'project_project', 'documents_folder_id IS NOT NULL')))
    ok &= _ee_report("DOCUMENTS (Documents -> OCA dms)", rows)

    # Studio: what goes with studio_customization (the port is in bgg_custom_dev 19.0.2.1.0)
    rows = []
    owned = _ee_owned_only(env, ('studio_customization',))
    env.cr.execute("SELECT model FROM ir_model WHERE id = ANY(%s)", [owned.get('ir.model', [])])
    studio_models = [model for (model,) in env.cr.fetchall()]
    env.cr.execute("SELECT model, name FROM ir_model_fields WHERE id = ANY(%s) AND store ORDER BY 1, 2",
                   [owned.get('ir.model.fields', [])])
    lost = []
    for model, name in env.cr.fetchall():
        # fields of a Studio model go with it (listed below)
        if model not in studio_models and model in env and env[model]._auto and name in env[model]._fields:
            filled = _ee_count(env, env[model]._table, '"%s" IS NOT NULL' % name)
            if filled:
                lost.append('%s.%s (%s rows)' % (model, name, filled))
    rows.append(('warn' if lost else 'ok', 'Studio fields with data, not taken over (deleted)',
                 '; '.join(lost) or 'none'))
    rows.append(('warn' if studio_models else 'ok', 'Studio models (deleted)', ', '.join(
        '%s (%s rows)' % (m, _ee_count(env, env[m]._table) if m in env else '?') for m in studio_models) or 'none'))
    for model, label in (('ir.actions.server', 'Studio server actions (deleted)'),
                         ('base.automation', 'Studio automation rules (deleted)')):
        recs = env[model].with_context(active_test=False).browse(owned.get(model, [])).exists() \
            if model in env else []
        active = [r for r in recs if 'active' not in r._fields or r.active]
        rows.append(('warn' if active else 'ok', label,
                     ', '.join(r.display_name for r in active) or 'none (or only inactive ones)'))
    views = env['ir.ui.view'].with_context(active_test=False).browse(owned.get('ir.ui.view', [])).exists()
    rows.append(('ok', 'Studio views (deleted; the ones we use are rebuilt in bgg_custom_dev)',
                 '%s, %s active' % (len(views), len(views.filtered('active')))))
    ok &= _ee_report("STUDIO (studio_customization goes with Enterprise)", rows)

    _ee_print("\n%s" % ("Ready for the uninstall ✅ (⚠️ : known, look at them once)" if ok else
                        "NOT READY ❌: fix the lines above before ee_uninstall"))
    env.cr.rollback()
    return ok


def ee_final_check(env):
    """Read-only. Before the dump: no Enterprise left, the Community
    modules installed, nothing that breaks the screens, counts kept."""
    from odoo.modules.module import get_module_path
    ok = True
    Module = env['ir.module.module']
    installed = Module.search([('state', '=', 'installed')])

    rows = [_ee_zero('Enterprise modules installed', len(_ee_module_names(env)), hint=', '.join(_ee_module_names(env)))]
    enterprise_code = [m.name for m in installed if '/enterprise/' in (get_module_path(m.name, display_warning=False) or '')]
    rows.append(_ee_zero('Installed modules from the Enterprise folder', len(enterprise_code),
                         hint=', '.join(enterprise_code)))
    no_code = [m.name for m in installed if not get_module_path(m.name, display_warning=False)]
    rows.append(_ee_zero('Installed modules whose code is not on this server', len(no_code),
                         hint=', '.join(no_code)))
    env.cr.execute("""SELECT count(*) FROM ir_model_data d JOIN ir_module_module m ON m.name = d.module
                       WHERE m.state = 'uninstalled' AND (m.license LIKE 'OEEL%%' OR m.name = ANY(%s))""",
                   [list(EE_EXIT_EXTRA_MODULES)])
    rows.append(_ee_zero('Records left by the uninstalled modules', env.cr.fetchone()[0], hint='run ee_cleanup(env)'))
    rows.append(_ee_pending_modules(env))
    rows += _ee_module_rows(env, EE_EXIT_TARGET_MODULES)
    for name in EE_EXIT_NOT_TAKEN:
        rows.append(('bad' if name in installed.mapped('name') else 'ok', 'Module %s (not taken)' % name,
                     'installed: uninstall it' if name in installed.mapped('name') else 'not installed'))
    ok &= _ee_report("MODULES", rows)

    rows = []
    env.cr.execute("""SELECT count(*) FROM ir_ui_menu WHERE web_icon IS NOT NULL
                       AND array_length(string_to_array(web_icon, ','), 1) <> 2""")
    rows.append(_ee_zero('App icons in Studio\'s format (black app menu)', env.cr.fetchone()[0],
                         hint='run ee_cleanup(env)'))
    valid = {value for value, __ in env['ir.ui.view']._fields['type'].selection}
    env.cr.execute("SELECT view_mode FROM ir_act_window WHERE view_mode IS NOT NULL")
    bad_modes = sum(1 for (mode,) in env.cr.fetchall() if any(m.strip() not in valid for m in mode.split(',') if m.strip()))
    rows.append(_ee_zero('Actions with a removed view type (gantt, map...)', bad_modes, hint='run ee_cleanup(env)'))
    types = env.ref('base.group_user') | env.ref('base.group_portal') | env.ref('base.group_public')
    users = env['res.users'].search([('active', '=', True)])
    no_type = users.filtered(lambda u: not (u.all_group_ids & types))
    rows.append(_ee_zero('Active users without a user type (cannot log in)', len(no_type), len(users),
                         hint=', '.join(no_type.mapped('login')[:10])))
    ok &= _ee_report("SCREENS AND USERS", rows)
    _ee_print("  conditions on removed fields:")
    _ee_fix_domains(env, dry_run=True)

    rows = []
    if 'resource.booking.type' in env:
        booking_types = env['resource.booking.type'].search([])
        rows.append(('ok' if booking_types else 'bad', 'Booking types', len(booking_types)))
        if 'x_group_ids' in env['resource.booking.type']._fields:
            nobody = booking_types.filtered(lambda t: not t.x_group_ids)
            rows.append(('warn' if nobody else 'ok', 'Booking types without "Réservable par"',
                         ', '.join(nobody.mapped('name')) or 'none'))
        group = env.ref('bgg_booking.group_booking_agent', raise_if_not_found=False)
        if group:
            bookers = env['res.users'].search([('active', '=', True), ('share', '=', False),
                                               ('all_group_ids', 'in', group.ids)])
            rows.append(('ok' if bookers else 'bad', 'Users who can book ("Prise de RDV")', len(bookers)))
    else:
        rows.append(('bad', 'Booking', 'bgg_booking not installed'))
    ok &= _ee_report("BOOKING (bgg_booking)", rows)

    folder = _ee_folder(env.cr.dbname)
    before_path = os.path.join(folder, 'counts_before.json')
    rows = []
    if os.path.exists(before_path):
        with open(before_path, encoding='utf-8') as f:
            before = json.load(f)
        losses = {}
        if os.path.exists(os.path.join(folder, 'expected_losses.json')):
            with open(os.path.join(folder, 'expected_losses.json'), encoding='utf-8') as f:
                losses = json.load(f)
        for label, count in _ee_survival_counts(env).items():
            old, loss = before.get(label), losses.get(label) or 0
            good = old is None or (count is not None and count >= old - loss)
            rows.append(('ok' if good else 'bad', label, '%s -> %s%s' % (old, count, '   (-%s expected)' % loss
                                                                           if loss else '')))
    else:
        rows.append(('warn', 'Counts before the uninstall', 'not found in %s' % folder))
    ok &= _ee_report("WHAT MUST SURVIVE: before the uninstall -> now", rows)

    neutralized = env['ir.config_parameter'].sudo().get_param('database.is_neutralized')
    _ee_print("\n  Database %s neutralized (%s)" % ('IS' if neutralized else 'is NOT',
              'rehearsal copy: emails and scheduled jobs off' if neutralized else 'production copy'))
    _ee_print("\n%s" % ("Ready for the dump ✅" if ok else "NOT READY ❌: fix the lines above before the dump"))
    env.cr.rollback()
    return ok
