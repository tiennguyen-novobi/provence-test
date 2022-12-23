from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    send_alert_email_template_id = fields.Many2one('mail.template', string='Email Template For Sending Alert',
                                                   related='company_id.send_alert_email_template_id', readonly=False)
