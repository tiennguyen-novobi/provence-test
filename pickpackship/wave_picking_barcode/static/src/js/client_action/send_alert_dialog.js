odoo.define('wave_picking_barcode.send_alert_dialog', function (require) {
    "use strict";

    let Dialog = require('web.Dialog');
    var core = require('web.core');
    var _t = core._t;

    var SendAlertDialog = Dialog.extend({
        template: 'send_alert_dialog_template',
        events: _.extend({}, Dialog.prototype.events, {
            'click button.btn_do_cycle_count': '_doCycleCount',
            'click button.btn_do_replenish_stock': '_doReplenishStock',
        }),
        init: function (parent, data) {
            this._super.apply(this, arguments);
            this.title = 'Send Alert';
            this.location = data.location;
            this.warehouse = data.warehouse;
            this.parent = parent;
            this.buttons = [
                {text: _t('YES, ALERT FOR CYCLE COUNT'), classes: 'btn_do_cycle_count btn-primary', click: function () {
                        this._doCycleCount();}},
                {text: _t('YES, ALERT FOR REPLENISH STOCK'), classes: 'btn_do_replenish_stock btn-primary', click: function () {
                        this._doReplenishStock();}},
                {text: _t('Close'), close: true}]
        },

        _doReplenishStock: function(){
            return this._send_email_to_alert("replenish stock")
        },

        _doCycleCount: function(){
            return this._send_email_to_alert("do cycle count")
        },

        _send_email_to_alert: function(action_name){
            var self = this;
            return this._rpc({
                'model': 'stock.location',
                'method': 'send_email_to_alert',
                'args': [[this.location.id], action_name, this.warehouse],
            }).then(function () {
                self.close();
                let wavePickingAbstractClientAction = self.parent.parent;
                wavePickingAbstractClientAction.do_notify(_t("Success"), _t("Sent an email to warehouse manager to " + action_name + " on " + self.location.name));
            }).guardedCatch(function () {
                let wavePickingAbstractClientAction = self.parent.parent;
                wavePickingAbstractClientAction.do_warn(_t("Error"), _t("Cannot send an email to warehouse manager"));
            });
        }
    })

    return SendAlertDialog;
})