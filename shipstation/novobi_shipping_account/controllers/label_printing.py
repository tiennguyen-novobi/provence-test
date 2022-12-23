# Copyright © 2021 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import base64
import os.path

from odoo.tools import pdf

from odoo import http, _


class PrintException(Exception):
    pass


class LabelPrinting(http.Controller):
    @http.route(
        ['/report/shipping/labels/shipping_label_and_packing_slip'],
        type='http',
        auth='user',
        methods=['GET'],
    )
    def report_shipping_label_and_packing_slip(self, picking_id, print_format='pdf'):
        assert print_format == 'pdf'
        picking = http.request.env['stock.picking'].browse(int(picking_id))
        return self.try_print_shipping_label_and_packing_slip_pdf(picking)

    @classmethod
    def try_print_shipping_label_and_packing_slip_pdf(cls, picking):
        try:
            return cls.print_shipping_label_and_packing_slip_pdf(picking)
        except PrintException as ex:
            return str(ex)

    @classmethod
    def print_shipping_label_and_packing_slip_pdf(cls, picking):
        report_binary = cls.get_shipping_label_and_packing_slip_for(picking)
        headers = cls.get_print_shipping_label_and_packing_slip_pdf_headers(picking, report_binary)
        response = http.request.make_response(report_binary, headers=headers)
        return response

    @classmethod
    def get_print_shipping_label_and_packing_slip_pdf_headers(cls, picking, report_binary):
        name = cls.get_print_shipping_label_and_packing_slip_pdf_name(picking)
        headers = [
            ('Content-Type', 'application/pdf; charset=utf-8'),
            ('Content-Length', len(report_binary)),
            ('Content-Disposition', http.content_disposition(name)),
        ]
        return headers

    @classmethod
    def get_print_shipping_label_and_packing_slip_pdf_name(cls, picking):
        return f'odoo_Shipping Label - {picking.partner_id.name or ""} - {picking.name}.pdf'

    @classmethod
    def get_shipping_label_and_packing_slip_for(cls, picking):
        packing_slip_binary = cls.get_packing_slip_report_for(picking)
        shipping_label_binary = cls.get_shipping_label_report_for(picking)
        return packing_slip_binary if not shipping_label_binary else pdf.merge_pdf(
            [packing_slip_binary, shipping_label_binary])

    @classmethod
    def get_shipping_label_report_for(cls, picking):
        label_attachment, is_attachment = picking.get_carrier_label_document()
        # cls.ensure_shipping_label_exists(label_attachment)
        # cls.ensure_shipping_label_pdf(label_attachment)
        return '' if not label_attachment else base64.b64decode(
            label_attachment.datas) if is_attachment else label_attachment

    @classmethod
    def ensure_shipping_label_exists(cls, label_attachment):
        if not label_attachment:
            raise PrintException(_('Unable to print label.'))

    @classmethod
    def ensure_shipping_label_pdf(cls, label_attachment):
        ext = os.path.splitext(label_attachment.name)[1][1:] or 'pdf'
        if ext.lower() != 'pdf':
            raise PrintException(_('Unsupported label format!'))

    @classmethod
    def get_packing_slip_report_for(cls, picking):
        report = cls.get_default_packing_slip_report()
        packing_slip_binary, t = report._render_qweb_pdf(picking.ids)
        return packing_slip_binary

    @classmethod
    def get_default_packing_slip_report(cls):
        return http.request.env.ref('novobi_shipping_account.action_report_packing_slip')
