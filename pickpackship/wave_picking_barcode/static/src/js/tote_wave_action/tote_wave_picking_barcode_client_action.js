odoo.define('wave_picking_barcode.ToteWavePickingClientAction', function (require) {
    'use strict';

    const EPSILON = 0.00001;
    var core = require('web.core');
    const {registry} = require("@web/core/registry");
    var WavePickingAbstractClientAction = require('wave_picking_barcode.WavePickingAbstractClientAction');
    var _t = core._t;
    var Dialog = require('web.Dialog');
    var ToteWaveLinesWidget = require('wave_picking_barcode.ToteWaveLinesWidget');
    var RemainingLinesWidget = require('wave_picking_barcode.RemainingLinesWidget');
    var EditLineWidget = require('wave_picking_barcode.EditLineWidget');
    var CreateWaveLabelWidget = require('wave_picking_barcode.CreateWaveLabelWidget');

    var ToteWavePickingClientAction = WavePickingAbstractClientAction.extend({

        custom_events: _.extend({}, WavePickingAbstractClientAction.prototype.custom_events, {
            check_done: '_isFullyReserved',
            check_finished_location: '_isFinishedLocation',
            scan_wave_label: '_scanWaveLabel',
            create_wave_label: '_onCreateWaveLabel',
            toggle_disable_button: '_onToggleDisableButton',
            toggle_hide_button: '_onToggleHideButton',
            toggle_primary_button: '_onTogglePrimaryButton',
            partially_validate: '_onPartiallyValidate',
            validate: '_onValidate',
            update_qty_done: '_onUpdateQtyDone',
            edit_line: '_onEditLine',
        }),

        initializeLinesWidget: function (data = {}) {
            this.linesWidget = new ToteWaveLinesWidget(this, data);
        },

        _step_location: function (barcode, linesActions) {
            let location = _.find(this.locations, function (location) {
                return location.barcode == barcode
            });
            if (location) {
                this.linesWidget._updateScannedLocationID(location.id);
                this.do_notify(_t("Success"), _t("Scan location successfully"));
                this.currentStep = 'product';
            } else {
                let errorMessage = _t("You are expected to scan a location in the batch.");
                return Promise.reject(errorMessage);
            }
            return Promise.resolve({linesActions: linesActions});
        },

        _step_product: function (barcode, linesActions) {
            let product = this.barcodetoProduct[barcode];
            let box = this.barcodetoBox[barcode];
            if (product || box) {
                let productID = box ? box.product_id : product.id;
                let qty = box ? box.qty : product.qty;
                let check_product_in_locations = this.datas[this.linesWidget.scannedLocationID]["products"][productID]
                if (check_product_in_locations) {
                    this.linesWidget.incrementProduct(productID, qty);
                } else {
                    let errorMessage = _t("This product does not belong to selected bin. Please scan a new product.");
                    return Promise.reject(errorMessage);
                }
            } else {
                return this._step_location(barcode, linesActions).then(function (res) {
                    return Promise.resolve({linesActions: res.linesActions});
                }, function () {
                    let errorMessage = _t("You are expected to scan a valid product.");
                    return Promise.reject(errorMessage);
                });
            }
            return Promise.resolve({linesActions: linesActions});
        },

        _step_wave_label: function (barcode, linesActions) {
            if (this.createWaveLabelWidget) {
                this.createWaveLabelWidget._updateWaveLabel(barcode);
                this.do_notify(_t("Success"), _t("Scan the batch label successfully"));
            } else {
                let errorMessage = _t("Can not scan the batch label");
                return Promise.reject(errorMessage);
            }
            return Promise.resolve({linesActions: linesActions});
        },

        _onUpdateQtyDone: function (ev) {
            ev.stopPropagation();
            let self = this;
            if (ev.data) {
                let product_data = this.datas[ev.data.locationID]["products"][ev.data.productID];
                let demand_qty = product_data['qty_done'] + ev.data.qty
                if (demand_qty > product_data['demand_qty']) {
                    self.do_warn(_t("Warning"), _t("This product has been fully picked. Please scan another one."));
                } else {
                    this._rpc({
                        model: 'stock.picking.batch',
                        method: 'update_wave_picking',
                        args: [[parseInt(this.waveID)], ev.data.locationID, ev.data.productID, ev.data.qty],
                    }).then(function (lineData) {
                        if (lineData) {
                            product_data['demand_qty'] = lineData['demand_qty'];
                            product_data['qty_done'] = lineData['qty_done'];
                            self.linesWidget.reloadLine(ev.data.domElement, lineData);
                            self.trigger_up('check_done');
                            self.do_notify(_t("Success"), _t("Scan product successfully."));
                        } else {
                            self.do_warn(_t("Error"), _t("Something went wrong while updating. Please try again!"));
                        }

                    })
                }

            }
        },

        _isFinishedLocation: function (ev) {
            let products = this.datas[ev.data.locationID].products;
            let isNotFinish = _.find(products, function (p) {
                return Math.abs(p.demand_qty - p.qty_done) > EPSILON;
            });
            if (!isNotFinish) {
                this.linesWidget._onClickNextLocation();
            }
            return !isNotFinish;
        },

        _isFullyReserved: function () {
            let self = this;
            let isFully = this.locations.every(function (location, index) {
                let products_lst = self.datas[location.id].products;
                let isNotFully = _.find(products_lst, function (p) {
                    return Math.abs(p.demand_qty - p.qty_done) > EPSILON;
                });
                return !isNotFully;
            });
            this.trigger_up('toggle_disable_button', {btnClass: '.o_partially_validate', isDisable: isFully});
            this.trigger_up('toggle_primary_button', {btnClass: '.o_validate', primary: isFully});
            return isFully;
        },

        _onToggleDisableButton: function (ev) {
            ev.stopPropagation();
            let btnClass = ev.data.btnClass;
            let isDisable = ev.data.isDisable;
            let $electedBtn = this.$(btnClass);
            $electedBtn.attr('disabled', isDisable);
        },

        _onToggleHideButton: function (ev) {
            ev.stopPropagation();
            let btnClass = ev.data.btnClass;
            let hide = ev.data.hide;
            let $electedBtn = this.$(btnClass);
            $electedBtn.toggleClass('o_hidden', hide);
        },

        _onTogglePrimaryButton: function (ev) {
            ev.stopPropagation();
            let btnClass = ev.data.btnClass;
            let primary = ev.data.primary;
            let $electedBtn = this.$(btnClass);
            $electedBtn.toggleClass('btn-secondary', !primary);
            $electedBtn.toggleClass('btn-primary', primary);
        },

        _onPartiallyValidate: function (ev) {
            let self = this;
            Dialog.confirm(this, (_t("Do you want to partially validate this batch?")), {
                confirm_callback: () => {
                    this._rpc({
                        model: 'stock.picking.batch',
                        method: 'force_validate',
                        args: [[parseInt(this.waveID)], false, ev.data.createNewWave],
                    }).then(function (res) {
                        if (res.success == true) {
                            self.do_notify(_t("Success"), _t("The transfer has been validated."));
                            if (res.new_batch_id) {
                                self.trigger_up('scan_wave_label', {new_wave_id: res.new_batch_id});
                            } else {
                                self.trigger_up('scan_wave_label');
                            }
                        } else {
                            self.do_warn(_t("Error"), _t("Something went wrong while validating this batch."));
                        }
                    }).guardedCatch(function () {
                        self.do_warn(_t("Error"), _t("Something went wrong while validating this batch."));
                    });
                }
            });
        },

        _onValidate: function (ev) {
            let self = this;

            if (this._isFullyReserved()) {
                this._rpc({
                    model: 'stock.picking.batch',
                    method: 'action_done',
                    args: [[parseInt(this.waveID)]]
                }).then(function () {
                    self.trigger_up('scan_wave_label');
                    self.do_notify(_t("Success"), _t("Validate successfully."));
                })
            } else {
                Dialog.confirm(this, (_t("This batch has not been fully picked. Do you want to validate?")), {
                    confirm_callback: () => {
                        this._rpc({
                            model: 'stock.picking.batch',
                            method: 'force_validate',
                            args: [[parseInt(self.waveID)], false, false],
                        }).then(function (res) {
                            if (res.success == true) {
                                if (res.not_done_moves_data) {
                                    let groups = _.groupBy(res.not_done_moves_data, function (m) {
                                        return m.product.id
                                    });
                                    let datas = _.map(groups, function (value, key) {
                                        let line = value[0]
                                        let demand_qty = 0;
                                        let quantity_done = 0;
                                        _.forEach(value, function (v) {
                                            demand_qty += v.demand_qty;
                                            quantity_done += v.quantity_done;
                                        });
                                        line.demand_qty = demand_qty;
                                        line.quantity_done = quantity_done;
                                        return {title: '', lines: [line]}
                                    });
                                    self.linesWidget.destroy();
                                    self.is_not_fully_pickied_screen = true;
                                    new RemainingLinesWidget(self, 'This batch has not been fully picked', datas).appendTo(self.$('.o_content'));
                                }
                            } else {
                                self.do_warn(_t("Error"), _t("Something went wrong while validating this batch."));
                            }
                        }).guardedCatch(function () {
                            self.do_warn(_t("Error"), _t("Something went wrong while validating this batch."));
                        });
                    }
                });
            }
        },

        _onEditLine: function (ev) {
            let productID = ev.data.productID;
            let qtyDone = ev.data.qtyDone;
            let reservedQty = ev.data.reservedQty;
            let locationID = ev.data.locationID;
            let productName = ev.data.productName;
            let uom = ev.data.uom;
            this.linesWidget.destroy();
            let data = {
                locationID: locationID,
                productID: productID,
                productName: productName,
                qtyDone: qtyDone,
                reservedQty: reservedQty,
                uom: uom
            }
            new EditLineWidget(this, data, 'stock.picking.batch', this.waveID).appendTo(this.$('.o_content'));
        },

        _scanWaveLabel: function (ev) {
            ev.stopPropagation();
            var self = this;
            if (this.wave_type == "tote") {
                this.linesWidget.destroy();
                this.currentStep = 'wave_label';
                this.is_scanning_batch_label = true;
                this.createWaveLabelWidget = new CreateWaveLabelWidget(this, ev.data.new_wave_id);
                this.createWaveLabelWidget.appendTo(this.$('.o_content'));
            } else if (ev.data.new_wave_id) {
                self._rpc({
                    model: 'stock.picking.batch',
                    method: 'open_wave_picking_client_action',
                    args: [[parseInt(ev.data.new_wave_id)]],
                }).then(function (action) {
                    self.do_action(action, {
                        'stackPosition': 'replaceCurrentAction'
                    });
                })
            } else {
                this.trigger_up('exit', {noConfirm: true});
            }
        },

        _onCreateWaveLabel: function (ev) {
            let self = this;
            ev.stopPropagation();
            this._rpc({
                model: 'stock.picking.batch',
                method: 'assign_wave_label',
                args: [[parseInt(this.waveID)], ev.data.wave_label]
            }).then(function (result) {
                if (result.error_message) {
                    self.do_warn(_t("Error"), _t(result.error_message));
                } else {
                    self.is_scanning_batch_label = false;
                    self.do_notify(_t("Success"), _t("The batch label was assigned to this batch."));
                    if (ev.data.new_wave_id) {
                        self._rpc({
                            model: 'stock.picking.batch',
                            method: 'open_wave_picking_client_action',
                            args: [[parseInt(ev.data.new_wave_id)]],
                        }).then(function (action) {
                            self.do_action(action, {
                                'stackPosition': 'replaceCurrentAction'
                            });
                        })
                    } else {
                        self.trigger_up('exit', {noConfirm: true});
                    }
                }
            })
        }

    })
    core.action_registry.add('tote_wave_picking_barcode_client_action', ToteWavePickingClientAction);
    return ToteWavePickingClientAction;

});


