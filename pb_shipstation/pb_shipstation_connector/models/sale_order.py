import logging

import psycopg2
from odoo.addons.multichannel_order.models.sale_order import MissingOrderProduct
from odoo.addons.queue_job.exception import RetryableJobError
from odoo.exceptions import ValidationError

from odoo import models, fields, api

_logger = logging.getLogger(__name__)

POUND_TO_KILOGRAM = 0.45359237
MILLIMETER_TO_INCH = 0.0393701


class SalesOrder(models.Model):
    _inherit = 'sale.order'

    ### PB-59 ###
    # channel is not from SS if channel_id (Store).shipstation_account_id is False
    shipstation_account_id_from_channel_id = fields.Many2one(related="channel_id.shipstation_account_id")

    ### PB-68 ###
    ship_by_on_shipstation = fields.Datetime(string="Ship By on ShipStation")

    @api.model
    def _sync_in_queue_job(self, order_data, channel_id, update):
        try:
            if update:
                self._update_in_queue_job(order_data, channel_id)
                order = self.sudo().search([('id_on_channel', '=', order_data['id_on_channel']),
                                            ('channel_id.id', '=', channel_id)])
            else:
                order = self.with_context(for_synching=True).create(self.flatten_order_data(order_data))
            order.ship_by_on_shipstation = order.commitment_date
            order.picking_ids.filtered(lambda p: p.state not in ('done', 'cancel')).write(
                {'scheduled_date': order.commitment_date, 'date_deadline': order.commitment_date})
        except MissingOrderProduct as e:
            raise e
        except (psycopg2.InternalError, psycopg2.OperationalError) as e:
            raise RetryableJobError(e)
        except Exception as e:
            raise e

    def action_confirm_pb(self):
        self.ensure_one()
        return self.env['ir.actions.actions']._for_xml_id(
            'pb_shipstation_connector.action_shipstation_confirm_order_wizard')

    def action_confirm(self):
        """
            Create a queue job to perform the two actions
        """
        res = super().action_confirm()
        # If an order from SS only generates <2 transfers, delete & import again
        if self.shipstation_account_id_from_channel_id and len(self.picking_ids) < 2:
            ids = [str(self.id_on_shipstation)]
            channel_id = self.channel_id.id
            obj = self.env['sale.order'].sudo().with_context(manual_import=True).with_delay()
            method = getattr(obj, "shipstation_get_data")
            method(channel_id=channel_id, ids=ids, from_date=None, to_date=None)
            self.action_cancel()
            self.unlink()
            return False
        return self.with_context().with_delay()._action_confirm_pb(res)

    def _action_confirm_pb(self, res):
        """
            Automatically buy labels for orders from SS only
        """

        for record in self:
            if record.platform != "amazon" and record.shipstation_account_id_from_channel_id:
                # Change request: Do not show popup for Odoo orders -> Do not automatically export/buy labels for these orders
                # Orders from Odoo do not have channel_id set, even if it has been exported to SS
                # Orders from SS have channel_id by default
                log = self.env['omni.log'].create({'channel_id': record.channel_id.id,
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
                        # 1. match package type
                        suitable_package_ids, _, _, _ = self.env["shipstation.shipping.rule"].find_suitable_packages(
                            out_picking)
                        if not suitable_package_ids:
                            # no rule can be matched
                            message = f"Label cannot be created automatically for <a href=# data-oe-model=stock.picking data-oe-id={out_picking.id}>{out_picking.name}</a>—no rules were matched. Please buy the label manually."
                            record.message_post(body=message)
                            log.update({"status": "failed", "message": message})
                            log.toogle_resolved()
                            continue

                        # 2. compare services
                        # assuming one SS account only
                        # TODO: ask for a default account to use if there are many?
                        out_picking.update(
                            {"shipstation_account_id": self.env["shipstation.account"].search([], limit=1).id})
                        suitable_services = list()
                        for pkg in suitable_package_ids:
                            out_picking.default_shipstation_stock_package_type_id = pkg
                            search_domain = [("delivery_type", "=", "shipstation"), ("ss_carrier_code", "=",
                                                                                     out_picking.default_shipstation_stock_package_type_id.package_carrier_type)]
                            if out_picking.partner_id.country_id.code == "US":
                                search_domain += [("is_domestic", "=", True)]
                            else:
                                search_domain += [("is_international", "=", True)]
                            suitable_delivery_carrier_id = record.env["delivery.carrier"].search(search_domain, limit=1)
                            if not suitable_delivery_carrier_id:
                                # maybe all the services for this carrier are not suitable
                                continue
                            out_picking.delivery_carrier_id = suitable_delivery_carrier_id
                            services = out_picking.delivery_carrier_id.with_context({}, overrideShipStation=True,
                                                                                    serviceCode="").get_rate_and_delivery_time(
                                picking=out_picking,
                                stock_package_type=out_picking.default_shipstation_stock_package_type_id,
                                package_length=out_picking.default_shipstation_stock_package_type_id.packaging_length * MILLIMETER_TO_INCH,
                                package_width=out_picking.default_shipstation_stock_package_type_id.width * MILLIMETER_TO_INCH,
                                package_height=out_picking.default_shipstation_stock_package_type_id.height * MILLIMETER_TO_INCH,
                                weight=out_picking.package_shipping_weight,
                                pickup_date=out_picking.shipping_date,
                                shipping_options="",
                                insurance_amount=out_picking.shipstation_insurance_amount)
                            services = list(filter(lambda s: s["serviceCode"] in [c.ss_service_code for c in
                                                                                  out_picking.shipstation_account_delivery_carrier_ids],
                                                   services))
                            if out_picking.partner_id.country_id.code == "US":
                                services = list(filter(lambda s: record.env["delivery.carrier"].search(
                                    [("delivery_type", "=", "shipstation"), ("ss_service_code", "=", s["serviceCode"])],
                                    limit=1).is_domestic, services))
                            else:
                                services = list(filter(lambda s: record.env["delivery.carrier"].search(
                                    [("delivery_type", "=", "shipstation"), ("ss_service_code", "=", s["serviceCode"])],
                                    limit=1).is_international, services))
                            if not services:
                                # no services for this pkg were matched, maybe because the carrier is not available for this account
                                continue
                            suitable_services.append((pkg, min(services, key=lambda s: s["shipmentCost"] + s["otherCost"])))

                        if not suitable_services:
                            # no services among all carriers are suitable
                            message = f"Label cannot be created automatically for <a href=# data-oe-model=stock.picking data-oe-id={out_picking.id}>{out_picking.name}</a>—no services were matched. Please buy the label manually."
                            record.message_post(body=message)
                            log.update({"status": "failed", "message": message})
                            log.toogle_resolved()
                            continue

                        selected_service = min(suitable_services, key=lambda s: s[1]["shipmentCost"] + s[1]["otherCost"])
                        out_picking.message_post(
                            body=f"""<b>Best services for each package:</b> {self.format_services_for_message_post(suitable_services)}<br/>
                            <b>Selected service:</b> {selected_service[1]['serviceName']}, {selected_service[0].name}
                            with total cost ${selected_service[1]['shipmentCost'] + selected_service[1]['otherCost']}""",
                            subject="Compare services")
                        data = {**data, **{"Selected service": selected_service[1]['serviceName'],
                                           "Cost": f"${selected_service[1]['shipmentCost'] + selected_service[1]['otherCost']}"}}
                        log.update({"datas": data})

                        # 3. update picking info with selected service
                        out_picking.default_shipstation_stock_package_type_id = selected_service[0]
                        out_picking.ss_carrier_code = out_picking.default_shipstation_stock_package_type_id.package_carrier_type
                        out_picking.delivery_carrier_id = record.env["delivery.carrier"].search(
                            [("delivery_type", "=", "shipstation"), ("ss_carrier_code", "=", out_picking.ss_carrier_code),
                             ("ss_service_code", "=", selected_service[1]["serviceCode"])],
                            limit=1)

                        # 4. buy shipping label
                        if out_picking.action_create_label():
                            data = {**data, **{"Shipment ID on ShipStation": out_picking.shipment_id_on_shipstation,
                                               "Carrier tracking reference": out_picking.carrier_tracking_ref}}
                            log.update({"status": "done", "datas": data,
                                        "message": f"Label created successfully for picking {out_picking.name}"})
                            record.message_post(
                                body=f"Label was automatically created successfully. Check the DO <a href=# data-oe-model=stock.picking data-oe-id={out_picking.id}>{out_picking.name}</a> for more details!")
                        else:
                            record.message_post(
                                body="Label cannot be automatically created. Check the logs for more details!")
                            log.update({"status": "failed",
                                        "message": "Label cannot be automatically created as something went wrong."})
                            log.toogle_resolved()
                except Exception as e:
                    log.update({"status": "failed", "message": str(e)})
                    log.toogle_resolved()
        return res

    def format_services_for_message_post(self, services):
        return '; '.join(
            f"{s[0].name, s[1]['serviceName'], s[1]['shipmentCost'] + s[1]['otherCost']}" for s in services)

    def export_single_order_to_shipstation(self, shipstation_store):
        if self.shipstation_account_id_from_channel_id:
            raise ValidationError(
                "This order is created from ShipStation. You cannot export to ShipStation after it is modified in Odoo.")
        super().export_single_order_to_shipstation(shipstation_store)
