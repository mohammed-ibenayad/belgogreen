# -*- coding: utf-8 -*-
"""Enterprise exit: uninstall the Odoo Enterprise modules.

Odoo shell script (not a module). On Odoo.sh, in the shell of the branch:

    odoo-bin shell --no-http
    exec(open('/home/odoo/src/user/tools/ee_exit/ee_uninstall.py').read())

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

import collections
import contextlib
import json
import os
import time

from odoo import api
from odoo.exceptions import UserError
from odoo.modules.registry import Registry
from odoo.tools import mute_logger

# Not under an Enterprise licence, but go with Enterprise: the bridge of
# bgg_custom_dev, the one-off Documents conversion, the Studio customizations.
EE_EXIT_EXTRA_MODULES = ('bgg_custom_dev_ee', 'bgg_documents_dms', 'studio_customization')

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
        if not recs:
            continue
        technical = model.startswith('ir.') or model in EE_EXIT_TECHNICAL or not Model._auto
        used, refs = set(), []
        if not technical:
            env.cr.execute("""
                SELECT cl.relname, a.attname, c.confdeltype
                  FROM pg_constraint c
                  JOIN pg_class cl ON cl.oid = c.conrelid
                  JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1]
                 WHERE c.contype = 'f' AND c.confrelid = %s::regclass
            """, [Model._table])
            for table, column, deltype in env.cr.fetchall():
                if table in dropped_tables or table.startswith('ir_'):
                    continue
                env.cr.execute('SELECT "%s", count(*) FROM "%s" WHERE "%s" = ANY(%%s) GROUP BY 1'
                               % (column, table, column), [recs.ids])
                rows = env.cr.fetchall()
                if rows:
                    used.update(r[0] for r in rows)
                    action = {'c': 'deleted with it', 'n': 'emptied', 'r': 'blocks', 'a': 'blocks'}.get(deltype, deltype)
                    refs.append('%s.%s: %s rows (%s)' % (table, column, sum(r[1] for r in rows), action))
        records[model] = {'records': recs, 'technical': technical, 'used': recs.browse(sorted(used)), 'refs': refs}

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
    return {'dropped_models': dropped_models, 'dropped_fields': dropped_fields, 'records': records,
            'selections': selections}


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

    _ee_print("\n=== WHAT MUST SURVIVE (now)")
    for label, count in _ee_survival_counts(env).items():
        _ee_print("  %-75s %s" % (label, '-' if count is None else count))
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
                    todo.button_immediate_uninstall()
                    _ee_print("    done in %.0f s" % (time.time() - start))
                break
            except UserError as error:   # a cron or another module operation running
                _ee_print("    busy (%s), retrying in 30 s" % error)
                time.sleep(30)
        else:
            raise UserError("Batch %s could not run. Stopped; run ee_uninstall again later." % label)

    # 5: compare
    with _ee_env(dbname) as env:
        left = _ee_module_names(env, keep)
        with open(before_path, encoding='utf-8') as f:
            before = json.load(f)
        after = _ee_survival_counts(env)
        _ee_print("\n=== WHAT MUST SURVIVE: before -> after")
        ok = True
        for label, count in after.items():
            old = before.get(label)
            good = old is None or (count is not None and count >= old)
            ok = ok and good
            _ee_print("  %s %-75s %s -> %s" % ('✅' if good else '❌', label, old, count))
        with open(os.path.join(folder, 'counts_after.json'), 'w', encoding='utf-8') as f:
            json.dump(after, f, ensure_ascii=False, indent=2)
        _ee_print("\nEnterprise modules still installed: %s" % (', '.join(left) or 'none ✅'))
        _ee_print("All counts kept ✅" if ok else "SOME COUNTS WENT DOWN ❌: check before going further")
