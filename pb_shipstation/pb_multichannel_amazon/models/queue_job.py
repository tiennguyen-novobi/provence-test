# Copyright © 2020 Novobi, LLC
# See LICENSE file for full copyright and licensing details.

import logging, datetime

from odoo import models, api, fields

_logger = logging.getLogger(__name__)


class QueueJob(models.Model):
    """Model storing the jobs to be executed."""
    _inherit = 'queue.job'

    @api.model
    def check_rate_limit_job(self):
        requeue_jobs = self.sudo().search([('state', '=', 'failed'), ('exc_info', 'ilike', 'amazon_api_helper.RateLimit')], limit=15)
        requeue_jobs.button_done()
        requeue_jobs.requeue()
        return True

    @api.model
    def check_pending_job(self):
        requeue_jobs = self.sudo().search(
            [('state', '=', 'pending'), ('date_created', '<=', fields.Datetime.now() - datetime.timedelta(hours=1))])
        if len(requeue_jobs) > 5000:
            return False
        requeue_jobs.button_done()
        requeue_jobs.requeue()
        return True

    @api.model
    def set_done_already_exists_job(self):
        done_jobs = self.sudo().search([('state', '=', 'failed')]).filtered(lambda j: j.exc_info and all(
            kw in j.exc_info for kw in ["Key", "id_on_channel", "channel_id", "already exists"]))
        done_jobs.button_done()
        return True
