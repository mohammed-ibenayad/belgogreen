# BelGoGreen WhatsApp Welcome Message (`bgg_whatsapp_welcome`)

Bridge module between the BelGoGreen welcome-call workflow and the Odoo **WhatsApp**
app (Enterprise). When the *"Welcom call"* project task is created — typically by the
project template when a sale order is confirmed — the module automatically queues a
pre-approved WhatsApp template message to the customer. The client therefore receives
a WhatsApp welcome message in addition to the phone welcome call, whose deadline is
already managed by `bgg_custom_dev` (order date + 2 days).

## How it works

1. A sale order is confirmed → the project template creates the *"Welcom call"* task.
2. `bgg_whatsapp_welcome` detects the task by its exact name (same convention as the
   deadline automation in `bgg_custom_dev`).
3. The customer is resolved from the task (`partner_id`), falling back to the sale
   order behind the task (`project_sale_order_id` → `sale_line_id` → project links).
4. The approved WhatsApp template is looked up by name and queued through the standard
   `whatsapp.composer`, so the message shows up in the **WhatsApp** app, the delivery
   is handled by the WhatsApp queue, and any customer reply opens a Discuss chat.
5. The task is flagged (`welcome_whatsapp_sent`) and a note is logged in its chatter.

A WhatsApp failure (template missing, no phone number, Meta error…) **never blocks**
task creation or sale order confirmation: the reason is logged in the task chatter and
the task form shows a **Send WhatsApp Welcome** button to retry manually. Project
managers get a **Resend** button (with confirmation) once a message was already sent.

## Configuration (system parameters)

*Settings → Technical → Parameters → System Parameters* (developer mode):

| Key | Default | Purpose |
|---|---|---|
| `bgg_whatsapp_welcome.enabled` | `True` | Master on/off switch (`False`/`0`/`no` disables) |
| `bgg_whatsapp_welcome.template_name` | `belgogreen_welcome_call` | Technical or display name of the WhatsApp template to send |
| `bgg_whatsapp_welcome.task_name` | `Welcom call` | Exact task name that triggers the automation |

## Prerequisites (one-time setup)

1. **Meta side** — WhatsApp Business Platform account, done by the client with our
   guide: [`docs/Guide_Client_WhatsApp_Meta.md`](../docs/Guide_Client_WhatsApp_Meta.md).
2. **Odoo side** — done by us once the client hands over their Meta values:
   1. *WhatsApp app → Configuration → WhatsApp Business Accounts → New*: fill in
      **App ID**, **App Secret**, **Access Token** (permanent system-user token),
      **Phone Number ID**, **Account ID** (WABA ID), then **Test Connection**.
   2. Copy the generated **Callback URL** + **Webhook Verify Token** back into the Meta
      app's webhook configuration and subscribe the webhook fields (`account_update`,
      `message_template_quality_update`, `message_template_status_update`, `messages`,
      `template_category_update`).
   3. *WhatsApp app → Templates → New*: create the `belgogreen_welcome_call` template
      (category **Utility**, language **French**, *Applies to* **Contact**, phone field
      `Phone`), e.g.:

      > Bonjour {{1}},
      >
      > Bienvenue chez BelGoGreen ! Votre dossier d'installation photovoltaïque est
      > ouvert. Un membre de notre équipe vous appellera dans les 2 jours ouvrables
      > pour faire connaissance et planifier les prochaines étapes.
      >
      > À très bientôt, l'équipe BelGoGreen

      with the variable `{{1}}` mapped to *Field of Model → Name*.
   4. **Submit for approval**, wait for Meta's approval e-mail, then **Sync Templates**
      on the WhatsApp business account.
   5. Install this module and confirm a test sale order to a number in the allowed
      test list (before the Meta app is Live) or to a real number (after go-live).

## Tests

```bash
odoo --test-enable -i bgg_whatsapp_welcome --test-tags=bgg_whatsapp_welcome
```

The tests mock the actual send, so they run without a connected WhatsApp account.

## Technical notes

- Depends on `whatsapp` (Odoo Enterprise), `project`, `sale_project`.
- The template may apply to **Contact** (recommended) or **Task**; other models are
  rejected with an explicit error.
- Sending uses `force_send_by_cron`, so the HTTP call to Meta happens outside the
  creation transaction.
