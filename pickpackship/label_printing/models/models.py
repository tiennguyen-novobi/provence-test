from odoo import models, _
from odoo.exceptions import ValidationError

class Base(models.AbstractModel):
    _inherit = 'base'

    def _get_printing_label_form(self, printing_service):
        """
        Get form view for printing action
        """
        return False

    def _update_printing_action_context(self, printing_service):
        """
        Get context for printing action
        """
        return {}

    def _get_printing_action(self, printing_service=None):
        action = self.env["ir.actions.actions"]._for_xml_id('label_printing.view_print_individual_record_label_create_action')
        action.update({
            'views': [(self._get_printing_label_form(printing_service), 'form')],
            'view_id': self._get_printing_label_form(printing_service)
        })
        return action

    def print_label(self):
        active_ids = self.ids or self.env.context.get('active_ids')

        printing_service = self.env['ir.config_parameter'].sudo().get_param('printing.service')
        if not printing_service:
            raise ValidationError(_('Please set up printing service (BarTender, QZ. or IoT Box).'))

        action = self._get_printing_action(printing_service)
        context = self.env.context.copy()
        context.update({
            'default_res_model': self._name,
            'default_res_ids': ','.join([str(e) for e in active_ids]),
            'default_copies': 1,
        })
        context.update(self._update_printing_action_context(printing_service))

        action.update({
            'context': context,
        })

        return action
