odoo.define('wave_picking_barcode.WavePickingAbstractClientAction', function (require) {
    'use strict';

    var concurrency = require('web.concurrency');
    var core = require('web.core');
    var AbstractAction = require('wave_picking_barcode.abstract_action_extend');
    var HeaderWidget = require('wave_picking_barcode.WaveHeaderWidget');
    var SoundsWidget = require('wave_picking_barcode.SoundsWidget');
    var _t = core._t;
    var Dialog = require('web.Dialog');
    var QWeb = core.qweb;

    var WavePickingAbstractClientAction = AbstractAction.extend({

        custom_events: {
            exit: '_onExit',
            listen_to_barcode_scanned: '_onListenToBarcodeScanned',
            reload: '_onReload'
        },

        _initializeData: function(action){
            this.title = action.params.title;
            this.datas = action.params.datas;
            this.orders = action.params.orders;
            this.pickings = action.params.pickings;
            this.barcodetoProduct = action.params.barcode_to_product;
            this.barcodetoBox = action.params.barcode_to_box;
            this.warehouse = action.params.warehouse;
            this.locations = action.params.locations;
            this.productSettings = action.params.product_settings;
            this.waveID = undefined;
            this.wave_type = undefined;
            this.is_manually_create = undefined;

            if (action.params.wave){
                this.waveID = action.params.wave.id;
                this.wave_type = action.params.wave.wave_type;
                this.is_manually_create = action.params.wave.is_manually_create;
            }

            this.orderIDs = _.map(this.orders, function (order) {
                return order.id
            });
            this.serialsLots = action.params.serials_lots;
            this.currentStep = undefined;
        },

        init: function (parent, action) {
            this._super.apply(this, arguments);

            this.actionManager = parent;
            this.mutex = new concurrency.Mutex();
            this._initializeData(action);
            // Steps
            this.currentStep = undefined;
            this.stepsByName = {};
            for (var m in this) {
                if (typeof this[m] === 'function' && _.str.startsWith(m, '_step_')) {
                    this.stepsByName[m.split('_step_')[1]] = this[m].bind(this);
                }
            }
            this.linesWidget = undefined;
            this.createWaveLabelWidget = undefined;
        },

        initializeLinesWidget: function(data={}){
            // Extend
        },

        _onReload: function(ev){
            let self = this;
            this._rpc({
                model: 'stock.picking.batch',
                method: 'open_batch_picking_client_action',
                args: [[parseInt(this.waveID)]],
            }).then(function (action) {
                self._initializeData(action);
                self.initializeLinesWidget(ev.data);
                self.loadContent();
            })
        },

        start: function () {
            var self = this;
            this.$('.o_content').addClass('o_barcode_client_action o_wave_picking_barcode_client_action');
            core.bus.on('barcode_scanned', this, this._onBarcodeScannedHandler);
            this.headerWidget = new HeaderWidget(this);
            this.soundsWidget = new SoundsWidget(this);
            this.initializeLinesWidget()
            return this._super.apply(this, arguments).then(function () {
                self.headerWidget.prependTo(self.$('.o_content')),
                self.soundsWidget.prependTo(self.$('.o_content'));
                self.loadContent();
            })
        },

        destroy: function () {
            core.bus.off('barcode_scanned', this, this._onBarcodeScanned);
            this.headerWidget.destroy();
            if (this.linesWidget != undefined){
                this.linesWidget.destroy();
            }
            this._super();
        },

        _exit: function(){
            let self = this;
            this.mutex.exec(function () {
                self.trigger_up('history_back');
            });
        },

        _onExit: function (ev) {
            ev.stopPropagation();
            var self = this;
            let noConfirm = ev.data.noConfirm;
            if (this.is_not_fully_pickied_screen){
                this.do_warn(_t('Error'), "Please click Close to proceed.");
            }
            else if (this.is_scanning_batch_label){
                this.do_warn(_t('Error'), "Please scan a batch label to proceed.");
            }
            else if (!noConfirm && this.waveID) {
                var confirming_message = _t("This action will delete all steps you have done for this batch. " +
                            "Do you want to continue ?");
                var cancel_batch = true;
                if (self.is_manually_create){
                    confirming_message = _t("This action will clear all steps you have done for this batch. " +
                                                "You can still re-open the batch to process it from the beginning. " +
                                                "Do you want to continue ?");
                    cancel_batch = false;
                }
                let dialogConfirm = new Dialog(this, {
                    title: _t('Confirmation'),
                    size: 'medium',
                    $content: QWeb.render('wave_barcode_confirmation', {
                        'message': confirming_message
                    }),
                    buttons: [
                        {text: _t('Yes'), click: function () {
                            dialogConfirm.close();
                            self._rpc({
                                model: 'stock.picking.batch',
                                method: 'clear_batch_picking',
                                args: [[parseInt(self.waveID)], cancel_batch],
                            }).then(function () {
                               self.mutex.exec(function () {
                                    self.trigger_up('history_back');
                               });
                            });
                        }, classes: 'btn-primary'
                    },
                    {text: _t('No'), close: true}
                ]}).open();
            } else {
                this._exit()
            }
        },

        _onBarcodeScannedHandler: function (barcode) {
            var self = this;
            this.mutex.exec(function () {
                if (self.mode === 'done' || self.mode === 'cancel') {
                    self.do_warn(_t('Warning'), _t('Scanning is disabled in this state.'));
                    return Promise.resolve();
                }
                return self._onBarcodeScanned(barcode);
            });
        },

        _onBarcodeScanned: function (barcode) {
            var self = this;
            return this.stepsByName[this.currentStep || 'location'](barcode, []).then(function (res) {
                return true
            }, function (errorMessage) {
                self.do_warn(_t('Warning'), errorMessage);
            })
        },
        /**
         * Handles the 'listen_to_barcode_scanned' OdooEvent.
         *
         * @private
         * @param {OdooEvent} ev ev.data.listen
         */
        _onListenToBarcodeScanned: function (ev) {
            if (ev.data.listen) {
                core.bus.on('barcode_scanned', this, this._onBarcodeScannedHandler);
            } else {
                core.bus.off('barcode_scanned', this, this._onBarcodeScannedHandler);
            }
        },

        loadContent: function(){
            if (this.linesWidget != undefined){
                this.linesWidget.appendTo(this.$('.o_content'));
            }
        },

    })

    return WavePickingAbstractClientAction;
});
