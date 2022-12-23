
import logging
from typing import Any
from .amazon_api_helper import AmazonHelper

_logger = logging.getLogger(__name__)

class AmazonReportHelper:
    _api: Any

    def __init__(self, channel):
        self._api = AmazonHelper.connect_with_channel(channel)

    def create_report(self, report_type, marketplace_ids):
        report_api = self._api.reports
        report = report_api.acknowledge(None)
        report.data = dict(reportType=report_type, marketplaceIds=marketplace_ids)
        res = report.publish()
        return res
    
    def get_report(self, report_id):
        report_api = self._api.reports
        report = report_api.acknowledge(report_id)
        res = report.get_by_id()
        return res
    
    def get_report_document(self, report_document_id):
        report_document_api = self._api.report_document
        report_document = report_document_api.acknowledge(report_document_id)
        res = report_document.get_by_id()
        return res
        