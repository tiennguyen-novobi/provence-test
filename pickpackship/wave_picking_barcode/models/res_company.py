from odoo import fields, models, _, api

class Company(models.Model):
    _inherit = 'res.company'

    send_alert_email_template_id = fields.Many2one('mail.template', string='Email Template For Sending Alert')
