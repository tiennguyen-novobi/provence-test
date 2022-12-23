from odoo.addons.web.controllers.main import ReportController
from odoo.http import route


class PdfPreviewController(ReportController):

    @route(['/report/download'], type='http', auth="user")
    def report_download(self, data, context=None):
        result = super().report_download(data, context=context)
        result.headers['Content-Disposition'] = result.headers['Content-Disposition'].replace('attachment', 'inline')
        return result
