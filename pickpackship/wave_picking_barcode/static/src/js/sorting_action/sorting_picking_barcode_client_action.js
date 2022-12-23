odoo.define('wave_picking_barcode.sorting_picking_barcode_client_action', function (require) {
    'use strict';

    var concurrency = require('web.concurrency');
    var core = require('web.core');
    var Dialog = require('web.Dialog');
    var AbstractAction = require('wave_picking_barcode.abstract_action_extend');
    var HeaderWidget = require('wave_picking_barcode.WaveHeaderWidget');
    var SortingLinesWidget = require('wave_picking_barcode.SortingLinesWidget');
    var SoundsWidget = require('wave_picking_barcode.SoundsWidget');
    var _t = core._t;
    var QWeb = core.qweb;

    var SortingClientAction = AbstractAction.extend({
        className: 'o_wave_client_action',

        custom_events: {
            exit: '_onExit',
            listen_to_barcode_scanned: '_onListenToBarcodeScanned',
            toggle_primary_button: '_onTogglePrimaryButton',
            update_qty_done: '_onUpdateQtyDone',
            reset_picking_bins: '_undoScanConfirmation',
            done_wave: '_doneWave'
        },

        initialValue: function(){
            this.currentStep = 'wave_label';
            this.stockMoveLineID = undefined;
            this.qtyDone = undefined;
            this.waveID = undefined;
            this.waveLabel = undefined;
            this.waveProducts = undefined;
            this.title = this.prefix_title;
            this.currentBinBarcode = undefined;
            this.scannedBin = undefined;
            this.isNewBin = undefined;
            this.scannedQty = 0;
        },

        init: function (parent, action) {
            this._super.apply(this, arguments);
            this.waveID = undefined;
            // Action params
            this.actionManager = parent;
            this.mutex = new concurrency.Mutex();
            this.title = action.params.title;
            this.prefix_title = action.params.title;
            this.currentStep = 'wave_label';
            this.stepsByName = {};
            for (var m in this) {
                if (typeof this[m] === 'function' && _.str.startsWith(m, '_step_')) {
                    this.stepsByName[m.split('_step_')[1]] = this[m].bind(this);
                }
            }
        },

        start: function () {
            var self = this;
            this.$('.o_content').addClass('o_barcode_client_action o_wave_picking_barcode_client_action');
            core.bus.on('barcode_scanned', this, this._onBarcodeScannedHandler);
            this.headerWidget = new HeaderWidget(this);
            this.sortingLinesWidget = new SortingLinesWidget(this);
            this.soundsWidget = new SoundsWidget(this);
            this.soundsWidget.prependTo(this.$el);
            return this._super.apply(this, arguments).then(function () {
                self.headerWidget.prependTo(self.$('.o_content'));
                self.sortingLinesWidget.appendTo(self.$('.o_content'));
                self.initialValue();
            })
        },

        destroy: function () {
            core.bus.off('barcode_scanned', this, this._onBarcodeScanned);
            this.headerWidget.destroy();
            if (this.sortingLinesWidget != undefined){
                this.sortingLinesWidget.destroy();
            }
            this._super();
        },

        _onExit: function (ev) {
            ev.stopPropagation();
            var self = this;
            if (this.waveID){
                let dialogConfirm = new Dialog(this, {
                    title: _t('Confirmation'),
                    size: 'medium',
                    $content: QWeb.render('wave_barcode_confirmation', {
                        'message': _t("All sorting has been saved. If the batch is not fully sorted, you can go back later, scan batch label, and continue sorting the remaining.")
                    }),
                    buttons: [
                        {text: _t('OK'), click: function () {
                            dialogConfirm.close();
                            self.mutex.exec(function () {
                                self.trigger_up('history_back');
                            });
                        }, classes: 'btn-primary'
                    },
                    {text: _t('Cancel'), close: true}
                ]}).open();
            } else{
                this.mutex.exec(function () {
                    self.trigger_up('history_back');
                });
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
            return this.stepsByName[this.currentStep || 'product'](barcode, []).then(function (res) {
                return true;
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

        _askNewBinConfirmation: function (qty, barcode) {
            let self = this;
            Dialog.confirm(this, _t("Do you want to add a new bin "+ barcode +" ?"), {
                confirm_callback: function () {
                    self.scannedBin = barcode;
                    self.isNewBin = true;
                    self.sortingLinesWidget.incrementProduct(self.stockMoveLineID, qty, barcode);
                },
            });
        },

        _step_bin: function(barcode, linesActions){
            // Check if add new bin to order or the existing one
            if (this.currentBinBarcode != '' && this.currentBinBarcode != undefined && this.currentBinBarcode.includes(barcode) == false){
                this._askNewBinConfirmation(this.qtyDone, barcode);
            } else {
                this.isNewBin = (this.currentBinBarcode == '' || this.currentBinBarcode == undefined) ? true : false;
                this.scannedBin = barcode;
                this.sortingLinesWidget.incrementProduct(this.stockMoveLineID, this.qtyDone, barcode);
            }
            return Promise.resolve({linesActions: linesActions});
        },

        _step_product: function(barcode, linesActions){
            let self = this;
            let product_info = {};
            if (self.waveProducts){
                product_info = self.waveProducts[barcode];
            }
            this._rpc({
                model: 'stock.picking',
                method: 'get_transfer_for_sorting',
                args: [[], product_info, barcode, self.waveID],
            }).then(function (data) {
                if (data.error_message != false){
                    let errorMessage = _t(data['error_message']);
                    self.do_warn(_t('Error'), errorMessage);
                }else if (data.wave){
                    self._load_wave(data.wave);
                }else{
                    self.scannedBin = undefined;
                    self.currentStep = 'bin';
                    self.sortingLinesWidget.reload(data, self.currentStep);
                    self.qtyDone = data['updated_qty_done'];
                    self.scannedQty = product_info['qty'];
                    self.stockMoveLineID = data['move_line_id'];
                    self.currentBinBarcode = data['picking_bins'];
                    self.do_notify(_t("Success"), _t("Scan the product successfully."));
                }
            }).guardedCatch(function (error) {
                let errorMessage = _t(error.message.data.message);
                self.do_warn(_t('Error'), errorMessage);
            });
            return Promise.resolve({linesActions: linesActions});
        },

        _load_wave: function(wave){
            this.waveID = wave.id;
            this.waveLabel = wave.wave_label;
            this.waveProducts = wave.wave_products;
            this.scannedBin = undefined;
            this.scannedQty = 0;
            this.title = this.prefix_title + ' - ' + this.waveLabel;
            this.headerWidget._reloadTitle(this.title);
            this.currentStep = 'product';
            this.sortingLinesWidget.reload(false, this.currentStep);
            this.do_notify(_t("Success"), _t("Scan the batch label successfully."));
        },

        _step_wave_label: function(barcode, linesActions){
            let self = this;
            this._rpc({
                model: 'stock.picking',
                method: 'get_wave_by_wave_label',
                args: [[], barcode],
            }).then(function (wave) {
                if (_.isEmpty(wave)){
                    let errorMessage = _t('You are expected to scan a valid batch label.');
                    self.do_warn(_t('Error'), errorMessage);
                } else{
                    self._load_wave(wave);
                }
            }).guardedCatch(function (error) {
                let errorMessage = _t(error.message.data.message);
                self.do_warn(_t('Error'), errorMessage);
            });
            return Promise.resolve({linesActions: linesActions});
        },

        _onTogglePrimaryButton: function(ev){
            ev.stopPropagation();
            let btnClass = ev.data.btnClass;
            let primary = ev.data.primary;
            let $electedBtn = this.$(btnClass);
            $electedBtn.toggleClass('btn-secondary', !primary);
            $electedBtn.toggleClass('btn-primary', primary);
        },

        _onUpdateQtyDone: function(ev){
            ev.stopPropagation();
            let self = this;
            if (ev.data) {
                this._rpc({
                    model: 'stock.move.line',
                    method: 'update_sorted_move_line',
                    args: [[ev.data.stockMoveLineID], ev.data.qtyDone, ev.data.toteBinBarcode, this.waveID],
                }).then(function (res) {
                    let lineData = res.line_data;
                    let waveCanBeDone = res.wave_can_be_done;
                    if (res.error_message){
                        let errorMessage = _t(res.error_message);
                        self.do_warn(_t('Error'), errorMessage);
                    }
                    else{
                        self.currentStep = 'product';
                        self.sortingLinesWidget.reload(lineData, self.currentStep);
                        self.trigger_up('toggle_primary_button', {btnClass: '.o_done_wave', primary: waveCanBeDone});
                        self.do_notify(_t("Success"), _t("Scan bin successfully."));
                    }
                }).guardedCatch(function (error) {
                    let errorMessage = _t(error.message.data.message);
                    self.do_warn(_t('Error'), errorMessage);
                });
            }
        },

        _isRemovedScannedBin: function () {
            let isRemovedScannedBin = (this.scannedBin && this.isNewBin) ? true : false;
            return isRemovedScannedBin;
        },

        _undoScanConfirmation: function () {
            let self = this;
            if (this.stockMoveLineID != undefined && this.scannedBin != undefined){
                let removeBin = this._isRemovedScannedBin() ? this.scannedBin : false;
                this._rpc({
                    model: 'stock.move.line',
                    method: 'reset_picking_bins',
                    args: [[this.stockMoveLineID], removeBin, this.scannedQty],
                }).then(function (data) {
                    self.currentStep = 'bin';
                    self.scannedBin = undefined;
                    self.sortingLinesWidget.reload(data, self.currentStep);
                    self.qtyDone = data['updated_qty_done'];
                    self.stockMoveLineID = data['move_line_id'];
                    self.currentBinBarcode = data['picking_bins'];
                    self.trigger_up('toggle_primary_button', {btnClass: '.o_done_wave', primary: false});
                    self.do_notify(_t("Success"), _t("Undo successfully."));
                }).guardedCatch(function (error) {
                    let errorMessage = _t(error.message.data.message);
                    self.do_warn(_t('Error'), errorMessage);
                });
            } else {
                this.do_warn(_t('Warning'), _t('There is not any order to undo.'));
            }
        },


        _doneWave: function () {
            let self = this;
            this._rpc({
                model: 'stock.picking.batch',
                method: 'clear_wave_label',
                args: [[this.waveID]],
            }).then(function(){
                self.initialValue();
                self.do_notify(_t("Success"), _t("Done the batch successfully."));
                self.trigger_up('toggle_primary_button', {btnClass: '.o_done_wave', primary: false});
                self.sortingLinesWidget.reload(undefined, self.currentStep);
            })
        },

    })

    core.action_registry.add('sorting_picking_barcode_client_action', SortingClientAction);

    return SortingClientAction;
});
