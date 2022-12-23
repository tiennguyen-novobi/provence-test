import logging

from odoo import models

_logger = logging.getLogger(__name__)


class SalesOrder(models.Model):
    _inherit = 'sale.order'

    def _action_confirm_pb(self, res):
        """
            Do not automatically export an order to ShipStation unless export_to_shipstation is set to store ID
            Automatically buy a label unless context variable no_create_label is set
        """
        res = super(SalesOrder, self)._action_confirm_pb(res)
        for record in self:
            if record._context.get("auto_buy", False) and record.platform == "amazon" and record.amazon_fulfillment_method == "MFN" and record.shipping_status == "unshipped":
                log = self.env['omni.log'].create({'channel_id': self.channel_id.id,
                                                   'entity_name': record.name,
                                                   'operation_type': 'auto_buy_label',
                                                   'res_model': 'sale.order',
                                                   'res_id': record.id,
                                                   'order_id': record.id,
                                                   'job_uuid': record._context.get("job_uuid")})
                data = dict()
                try:
                    out_pickings = record.picking_ids.filtered(
                        lambda p: p.picking_type_code == "outgoing" and p.state != "cancel")
                    for out_picking in out_pickings:
                        # just in case the SO already has >1 DO right when the user confirms
                        # e.g., when backorders were created for DO, then the SO is cancelled and is confirmed again
                        # which is extremely rare
                        out_picking.update(out_picking._set_default_vals_label_form())
                        # 1. match package dimensions
                        _, pkg_length, pkg_width, pkg_height = self.env[
                            "shipstation.shipping.rule"].find_suitable_packages(out_picking)
                        if not pkg_length:
                            # no rule can be matched
                            message = f"Label cannot be created automatically for <a href=# data-oe-model=stock.picking data-oe-id={out_picking.id}>{out_picking.name}</a>—no rules were matched. Please buy the label manually."
                            record.message_post(body=message)
                            log.update({"status": "failed", "message": message})
                            log.toogle_resolved()
                            continue

                        out_picking.amazon_get_rate_and_delivery_time()
                        suitable_service_id = self.env["suitable.service"].search([("picking_id", "=", out_picking.id)],
                                                                                  limit=1)
                        out_picking.suitable_service_id = suitable_service_id
                        if not out_picking.suitable_service_id:
                            # no service returned
                            message = f"Label cannot be created automatically for <a href=# data-oe-model=stock.picking data-oe-id={out_picking.id}>{out_picking.name}</a>—no services were returned. Please buy the label manually."
                            record.message_post(body=message)
                            log.update({"status": "failed", "message": message})
                            log.toogle_resolved()
                            continue
                        out_picking.with_context(auto_buy=True).amazon_create_shipment_label()

                        data = {**data, **{"Service": out_picking.suitable_service_id.name,
                                           "Shipment ID on Amazon": out_picking.shipment_id_on_amazon,
                                           "Carrier tracking reference": out_picking.carrier_tracking_ref}}
                        log.update({"status": "done", "datas": data,
                                    "message": f"Label created successfully for picking {out_picking.name}"})
                        record.message_post(
                            body=f"Label was automatically created successfully. Check the DO <a href=# data-oe-model=stock.picking data-oe-id={out_picking.id}>{out_picking.name}</a> for more details!")
                except Exception as e:
                    log.update({"status": "failed", "message": str(e)})
                    log.toogle_resolved()
            if record.amazon_fulfillment_method == "AFN":
                record.picking_ids.filtered(lambda r: r.state not in ('done', 'cancelled')).action_cancel()
        return res


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def write(self, values):
        res = super(SaleOrderLine, self).write(values)
        for record in self:
            if record.order_id.amazon_fulfillment_method == "AFN":
                # cancel newly created pickings (especially when order lines are updated)
                record.order_id.picking_ids.filtered(lambda r: r.state not in ('done', 'cancelled')).action_cancel()
        return res

