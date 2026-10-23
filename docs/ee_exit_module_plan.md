# Enterprise exit: plan per module

What happens to each of the 129 Enterprise modules installed on production
(extract of staging, 2026-10-23). The uninstall script follows this file.
Data counts come from the read-only audit run on staging.

## 1. Data already moved to our modules (uninstall once moved)

| Modules | Enterprise data | Moved to |
|---|---|---|
| appointment, appointment_account_payment, appointment_crm, appointment_hr, appointment_hr_recruitment, appointment_sms, website_appointment, website_appointment_account_payment, website_appointment_crm | 7 types, 43 questions, 92,356 answers, 33,032 booking lines; RDV type/status/booker on 35,817 events | bgg_custom_dev (`x_rdv_*` fields, RDV types with their commercials) and bgg_booking (call-centre booking on OCA resource_booking) |
| documents, documents_account, documents_fleet, documents_fsm, documents_hr, documents_hr_expense, documents_product, documents_project, documents_project_sale, website_documents, ai_documents, ai_documents_account, ai_documents_source | 9,319 documents, access, tags, project folders | OCA dms (bgg_documents_dms conversion, bgg_dms, bgg_dms_project) |
| web_studio, website_studio (and studio_customization) | Studio fields, views, actions, filters | bgg_custom_dev 19.0.2.1.0 (Studio port) |
| industry_fsm, industry_fsm_sale, industry_fsm_report, industry_fsm_sale_report, industry_fsm_sms, worksheet | "Field Service" flag on 894 projects | bgg_custom_dev `x_is_sss_project`, `x_sss_sale_order_id`; SSS tasks are plain project tasks |
| sale_commission | 14 plans, 64 users, 56 targets | Not moved: replaced by belgogreen_sales_commission (own plans) |

Field Service, before uninstall:
- **7 tasks** marked done in Field Service are still open in Community
  terms: the uninstall script closes them (state "done") first.
- Dropped (not used): 2 worksheets and their template, planned start dates
  of 5,106 tasks (deadlines stay), "under warranty" (1 task), "allow
  material" (10 projects).

## 2. Dropped (decided)

| Area | Modules | Lost |
|---|---|---|
| Accounting (Enterprise part) | account_accountant, account_accountant_fleet, account_asset, account_asset_fleet, account_bank_statement_extract, account_bank_statement_import, account_bank_statement_import_camt, account_bank_statement_import_csv, account_bank_statement_import_ofx, account_base_import, account_extract, account_fiscal_categories, account_fiscal_categories_fleet, account_followup, account_invoice_extract, account_invoice_extract_purchase, account_loans, account_online_synchronization, account_reports, account_transfer, accountant, accountant_fleet, accountant_hr_expense, analytic_enterprise, purchase_accountant, sale_account_accountant, snailmail_account_followup, project_account_asset, currency_rate_live, hr_expense_extract, hr_expense_predict_product, spreadsheet_dashboard_account_accountant | 42 assets, 142 tax returns (507 checks), 2 follow-up levels, bank sync (5 accounts), invoice OCR data, deferred entries settings. Invoices, payments, bank statements and journal items are Community data and **stay**. |
| Belgian / French reports | l10n_be_coda, l10n_be_soda, l10n_be_fiscal_categories, l10n_be_intervat, l10n_be_reports, l10n_be_reports_client_nihil, l10n_be_reports_sms, l10n_fr_reports | Intervat link, VAT/ISOC reports, CODA/SODA import (replacement depends on the open "bank" decision) |
| AI | ai, ai_account, ai_auto_install, ai_knowledge, ai_website, hr_recruitment_ai | 3 agents, 22 prompt buttons |
| Marketing | marketing_automation, marketing_automation_crm, marketing_automation_sms, social, social_crm, social_facebook, social_instagram, social_linkedin, social_push_notifications, social_sale, social_twitter, social_youtube | 2 campaigns, 355 social posts |
| Spreadsheets | spreadsheet_edition, spreadsheet_dashboard_edition, spreadsheet_dashboard_documents, spreadsheet_dashboard_crm, spreadsheet_sale_management, documents_spreadsheet | 8 user dashboards (2 edited), spreadsheet edits. Dashboards are bgg_custom_dev's own; Community `spreadsheet_dashboard` stays (bgg_custom_dev depends on it). |
| Planning, timesheets, views | project_enterprise, project_enterprise_hr, project_enterprise_hr_skills, hr_gantt, timesheet_grid, sale_timesheet_enterprise, timer, web_gantt, web_grid, web_cohort, web_map | Gantt/grid/map/cohort views, timesheet reminders and validation screens. Timesheet lines (4,586) are Community and stay. |
| Other | hr_recruitment_extract, hr_recruitment_reports, iap_extract, product_barcodelookup, crm_enterprise, sale_enterprise, contacts_enterprise, digest_enterprise, mail_enterprise, web_enterprise, website_enterprise, web_mobile, mail_mobile, hr_mobile | OCR of CVs, Enterprise look and mobile app push |

## 3. Waiting

| Modules | Data | Status |
|---|---|---|
| whatsapp, whatsapp_account, whatsapp_account_followup, whatsapp_calendar, whatsapp_payment, whatsapp_sale, marketing_automation_whatsapp | 2 Meta accounts, 17 templates, 30 messages; **8 active "Welcome call" automation rules** (rules 20-27 on sale orders: one WhatsApp template per company and payment term when an order is confirmed) | Wait for OCA `mail_gateway_whatsapp` 19.0 (OCA/mail PR #203, open). See open decisions. |
| knowledge, website_knowledge | 227 articles, 83 members, 59 favourites | Later: OCA document_page |

## 4. Uninstall script: to include

- Close the 7 Field Service tasks done but still open.
- Before WhatsApp goes: save the Meta account details (app, business
  account and phone number ids) and the 17 template definitions (name,
  language, body, variables) to a file, to set up WhatsApp again on
  Community. The welcome-call rules (20-27) lose their WhatsApp action:
  archive them.
- Inactive automation rules 1-19 (old versions of what was ported to
  bgg_custom_dev): the 5 on appointment answers go with Appointments; the
  others can be deleted.
- Row counts before / after on what must survive: sale orders, invoices and
  payments, calendar events and their RDV fields, projects and tasks, DMS
  folders and files, partners, users, commissions.
