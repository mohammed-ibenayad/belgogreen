from odoo import models, fields, api
import re

class UserFeedback(models.TransientModel):
    _name = 'user.feedback'
    _description = 'User Feedback Collection'

    feedback = fields.Text(string="Your Feedback", required=True)
    email = fields.Char(string="Your email for getting updates")
    wants_updates = fields.Boolean(string="Notify me when released", default=True)

    @api.constrains('email')
    def _validate_email(self):
        for record in self:
            if record.email and not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', record.email):
                raise models.ValidationError("Please enter a valid email address")

    def submit_feedback(self):
        # Send email to admin
        admin_email = "mohammed.ibenayad@gmail.com"  # <-- CHANGE TO YOUR EMAIL
        subject = f"New Feedback for LLM Reports Module"
        body = f"""
        <p>New feedback received:</p>
        <p><strong>Feedback:</strong></p>
        <p>{self.feedback}</p>
        {"<p><strong>User wants updates at:</strong> " + self.email + "</p>" if self.wants_updates else ""}
        """

        self.env['mail.mail'].sudo().create({
            'subject': subject,
            'body_html': body,
            'email_to': admin_email,
            'email_from': self.email or "noreply@yourdomain.com",
        }).send()

        # Confirmation message
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Thank You!',
                'message': 'Feedback submitted.' + 
                          (' We will notify you!' if self.wants_updates else ''),
                'type': 'success',
                'sticky': False,
            }
        }