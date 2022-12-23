

odoo.define('packing_barcode_printing.packing_barcode_printing_client_action', function (require) {
    'use strict';

    const core = require('web.core');
    const PackingBarcodeClientAction = require('packing_barcode.packing_barcode_client_action');
    const _t = core._t;
    let DeviceProxy = require('iot.DeviceProxy');

    const PackingBarcodePrintingClientAction = PackingBarcodeClientAction.include({
        initializeValueForPrinting: function(action) {
            // Initialize default values for printing
            this.pickedPrinter = action.context.printer;
            this.printingService = action.context.printing_service;
        },

        _onValueChange: function (data) {
            if (data.status) {
                this.do_notify(false, _t("Printer ") + data.status);
            }
        },

        _onIoTActionResult: function (data){
            if (data.result === true) {
                this.do_notify(false, _t('Successfully sent to printer!'));
            } else {
                this.do_warn(_t('Connection to printer failed'), _t('Check if the printer is still connected'));
            }
        },

        _onIoTActionFail: function (ip){
            // Display the generic warning message when the connection to the IoT box failed.
            this.call('iot_longpolling', '_doWarnFail', ip);
        },

        _printLabelsByIoT: function (iot_ip, identifier, document){
            let self = this;
            let iot_device = new DeviceProxy(self, {iot_ip: iot_ip, identifier: identifier});
            iot_device.add_listener(this._onValueChange.bind(self));
            iot_device.action({'document': document})
                .then(function(data) {
                    self._onIoTActionResult.call(self, data);
                }).guardedCatch(
                    self._onIoTActionFail.bind(self, iot_ip));
        },

        _onPrintLabel: function(ev){
            if (this.printingService){
                let self = this;
                if (!this.labels){return this.do_warn(_t("Error"), _t("There are no label created for this order."));}
                if (!this.pickedPrinter){return this.do_warn(_t("Error"), _t("Missing selected device."));}
                if (this.printingService == 'iot'){
                    _.each(this.labels, function(label){
                        self._printLabelsByIoT(self.pickedPrinter.iot_ip, self.pickedPrinter.identifier, label);
                    })
                }
                return true;
            }
            return false;
        }

    })

    return PackingBarcodePrintingClientAction;
});
