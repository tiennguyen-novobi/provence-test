from odoo import fields, models, api, _


class ShipStationAccount(models.TransientModel):
    _inherit = 'res.config.settings'

    shipstation_installed = fields.Boolean(string='ShipStation Integration', config_parameter='shipstation_installed')

    def open_shipstation_account(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("shipstation_connector.action_shipstation_account")
        return action
