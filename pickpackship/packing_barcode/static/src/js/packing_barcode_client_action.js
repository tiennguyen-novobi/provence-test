odoo.define('packing_barcode.packing_barcode_client_action', function (require) {
    'use strict';

    var core = require('web.core');
    var LinesWidget = require('packing_barcode.LinesWidget');
    var WavePickingAbstractClientAction = require('wave_picking_barcode.WavePickingAbstractClientAction');
    var _t = core._t;
    let Dialog = require('web.Dialog');

    var PackingBarcodeClientAction = WavePickingAbstractClientAction.extend({
        className: 'o_packing_barcode_client_action',

        custom_events: {
            exit: '_onExit',
            validate: '_onValidate',
            skip_packing: '_onSkipPacking',
            print_label: '_onPrintLabel'
        },

        init: function (parent, action) {
            this._super.apply(this, arguments);
            this.actionManager = parent;
            this.title = 'Shipping';
            this.currentStep = 'product';
            this.isSinglePicking = false;

            this.commands = {}
            this.commands['O-BTN.validate'] = this._onValidate.bind(this);

            this.initializeValueForPrinting(action)
        },

        start: function () {
            this.linesWidget = new LinesWidget(this);
            return this._super.apply(this, arguments);
        },

        initializeValueForPrinting: function(action) {
            // Initialize default values for printing
            // this.pickedPrinter = action.context.printer;
            // this.printingService = action.context.printing_service;
        },

        _onBarcodeScannedHandler: function (barcode) {
            var self = this;
            this.mutex.exec(function () {
                if (self.mode === 'done' || self.mode === 'cancel') {
                    self.do_warn(_t('Warning'), _t('Scanning is disabled in this state.'));
                    return Promise.resolve();
                }

                var commandeHandler = self.commands[barcode];
                if (self.pickingID && commandeHandler) {
                    return commandeHandler();
                }

                return self._onBarcodeScanned(barcode);
            });
        },

        _printLabels: function(labels){
            return true
        },

        _exit: function(){
            if (this.pickingID && this.isSinglePicking) {
                this._rpc({
                    model: 'single.packing.queue',
                    method: 'insert_record',
                    args: [this.pickingID],
                })
            }
            this._super.apply(this, arguments);
        },

        _updateShippingData: function (data) {
            this.pickingID = data.pickingID;
            this.shippingID = data.shippingID;
            this.weight = data.shipping_weight;
            this.shipDate = data.ship_date;
            this.isSinglePicking = data.isSinglePicking;
            this.labels = data.labels;
        },

        _step_product: function(barcode, linesActions){
            let self = this;
            return this._rpc({
                model: 'stock.picking',
                method: 'get_transfer_for_shipping',
                args: [barcode, this.isSinglePicking, this.pickingID],
            }).then(function (data) {
                if (data){
                    self._updateShippingData(data);
                    self.linesWidget.reload(data);
                    self.trigger_up('print_label');
                }else{
                    self.do_warn(_t("Error"), _t("No order is ready for shipping."));
                }
                return Promise.resolve({linesActions: linesActions})
            }).guardedCatch(function () {
                return Promise.resolve({linesActions: linesActions})
            });

        },

        _onValidate: function (ev) {
            let self = this;
            this._rpc({
                model: 'stock.picking',
                method: 'done_and_print_label',
                args: [[parseInt(self.pickingID)]],
            }).then(function (res) {
                if (res.success){
                    self.pickingID = undefined;
                    self.linesWidget.toggleButton(true, false, true);
                    self.do_notify(_t("Success"), _t("Validate successfully"));
                } else{
                    self.do_warn(_t("Error"), _t(res.error_message));
                }

            }).guardedCatch(function () {
                self.do_warn(_t("Error"), _t("Something went wrong while validating this batch."));
            });
        },

        _onSkipPacking: function(ev){
            let self = this;
            Dialog.confirm(this, _t("Are you sure you want to put on hold this order ?"), {
                confirm_callback: function () {
                    self._rpc({
                        model: 'stock.picking',
                        method: 'action_hold_shipping',
                        args: [[parseInt(self.pickingID)]],
                    }).then(function () {
                        self.do_notify(_t("Success"), _t("Put on hold the Shipping successfully"));
                        self.pickingID = undefined;
                        self.linesWidget.do_clean();
                    }).guardedCatch(function () {
                        self.do_warn(_t("Error"), _t("Something went wrong while validating this batch."));
                    });
                },
            });  
        },

        _onPrintLabel: function(ev){

        }

    })

    core.action_registry.add('packing_barcode_client_action', PackingBarcodeClientAction);

    return PackingBarcodeClientAction;
});
