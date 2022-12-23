from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    label_width = fields.Integer("Label Width",
                                 config_parameter='printing.label.width')

    label_height = fields.Integer("Label Height",
                                  config_parameter='printing.label.height')

    printer_dpi = fields.Selection([('203', '203 dpi'),
                                    ('300', '300 dpi')],
                                   config_parameter='printing.dpi',
                                   string="Printer DPI")

    module_printing_by_bartender = fields.Boolean(string='BarTender')
    module_printing_by_qz = fields.Boolean(string='QZ.')
    module_printing_by_iot = fields.Boolean(string='IoT Box')

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        if self.module_printing_by_bartender:
            self.env['ir.config_parameter'].set_param('printing.service', 'bartender')
        elif self.module_printing_by_qz:
            self.env['ir.config_parameter'].set_param('printing.service', 'qz')
        elif self.module_printing_by_iot:
            self.env['ir.config_parameter'].set_param('printing.service', 'iot')
        else:
            self.env['ir.config_parameter'].set_param('printing.service', False)
