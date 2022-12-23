odoo.define('wave_picking_barcode.OrderWavePickingClientAction', function (require) {
    'use strict';

    const EPSILON = 0.00001;
    var core = require('web.core');
    var WavePickingAbstractClientAction = require('wave_picking_barcode.WavePickingAbstractClientAction');
    var Dialog = require('web.Dialog');
    var _t = core._t;
    var QWeb = core.qweb;
    var OrderWaveLinesWidget = require('wave_picking_barcode.OrderWaveLinesWidget');
    var RemainingLinesWidget = require('wave_picking_barcode.RemainingLinesWidget');
    var EditLineWidget = require('wave_picking_barcode.EditLineWidget');

    var OrderWavePickingClientAction = WavePickingAbstractClientAction.extend({

        custom_events: _.extend({}, WavePickingAbstractClientAction.prototype.custom_events, {
            validate: '_onValidate',
            reset: '_onReset',
            toggle_button: '_onToggleButton',
            toggle_disable_button: '_onToggleDisableButton',
            check_finished_location: '_isFinishedLocation',
            check_done: '_isFullyReserved',
            update_scanned_serial_numbers: '_onUpdateScannedSerialNumbers',
            edit_line: '_onEditLine',
        }),

        init: function (parent, action) {
            this._super.apply(this, arguments);
            this.toteBinToOrder = {};
            this.orderToteBins = action.params.order_tote_bins || {};
            this.scannedBins = [];
            this.scannedSerialNumbers = {};
            this.scannedQty = 0;
            this.scannedMoveLine = undefined;
        },

        _initializeData: function(action){
            this._super.apply(this, arguments);
            this.scannedQty = 0;
            this.scannedMoveLine = undefined;
        },

        initializeLinesWidget: function(data={}){
            this.linesWidget = new OrderWaveLinesWidget(this, data);
        },

        start: function () {
            return this._super.apply(this, arguments)
        },

        _updateToteBin: function (barcode, orderID, moveLineID) {
            let self = this;
            this.toteBinToOrder[barcode] = orderID;
            this.scannedBins.push(barcode);
            this.orderToteBins[orderID] = this.orderToteBins[orderID] || [];
            this.orderToteBins[orderID].push(barcode);

            // Update bins
            let bins = this.orderToteBins[orderID].join(',');
            return this._rpc({
                model: 'stock.move.line',
                method: 'update_picking_bins',
                args: [[parseInt(moveLineID)], bins],
            }).then(function () {
                self.linesWidget._renderLines();
                self.do_notify(_t("Success"), _t('Add bin ' + barcode + ' successfully.'));
            });

        },

        _step_tote_bin: function (barcode, linesActions) {
            let self = this;
            let orderID = this.scannedMoveLine.picking.sale_id;
            let moveLineID = this.scannedMoveLine.move_line_id;
            // Whether or not this tote bin is using for another order
            let existedBinBarcode = _.find(this.scannedBins, function(bin){
                return barcode == bin
            });

            if (existedBinBarcode && this.toteBinToOrder[existedBinBarcode] != orderID){
                return Promise.reject(_t("This bin has been assigned to another order. Please scan another one."));
            }

            let bins = this.orderToteBins[orderID] || [];

            let bin = _.find(bins, function (bin) {
                return barcode == bin
            });

            if (bin && bins.length > 0) {
                this.linesWidget.incrementProduct(moveLineID, this.scannedQty).then(function () {
                    self.scannedMoveLine = undefined;
                    self.currentStep = 'product';
                    self.do_notify(_t("Success"), _t('Add product to bin ' + barcode + ' successfully.'));
                }, function(){
                    self.do_notify(_t("Success"), _t('Scan Tote bin ' + barcode + ' successfully.'));
                });
            }else if (bins.length == 0){
                this._updateToteBin(barcode, orderID, moveLineID).then(function(){
                    self.linesWidget.incrementProduct(moveLineID, self.scannedQty).then(function () {
                        self.scannedMoveLine = undefined;
                        self.currentStep = 'product';
                    })
                });
            }else {
                var success = function (res) {
                    if (res) return Promise.resolve({linesActions: res.linesActions});
                    return true;
                };

                var fail = function () {
                    let order = _.find(self.orders, function (o) {
                        return o.id == orderID;
                    });
                    let dialog = new Dialog(self, {
                        title: _t('Confirmation'),
                        size: 'medium',
                        $content: QWeb.render('change_bin_warning', {toteBinBarcode: barcode, order: order}),
                        buttons: [
                            {
                                text: _t('Yes'), classes: 'btn-submit btn-primary', click: function () {
                                    // Add a new Tote Bin to order
                                    self._updateToteBin(barcode, orderID, moveLineID).then(function(){
                                        self.linesWidget.incrementProduct(moveLineID, self.scannedQty).then(function(){
                                            self.scannedMoveLine = undefined;
                                            self.currentStep = 'product';
                                        });
                                    });
                                    dialog.close();
                                }
                            },
                            {text: _t('No'), close: true},
                        ]
                    }).open();
                }

                return self._step_product(barcode, linesActions).then(success, function () {
                    return self._step_serial_number(barcode, linesActions).then(success, fail)
                });
            }

            return Promise.resolve({linesActions: linesActions});
        },

        _isProductExisted: function(barcode){
            let product = this.barcodetoProduct[barcode];
            let box = this.barcodetoBox[barcode];
            return product || box
        },

        _findMoveLine: function (barcode) {
            let moveLine = undefined;
            let product = this.barcodetoProduct[barcode];
            let box = this.barcodetoBox[barcode];
            if (product || box) {
                let productID = box ? box.product_id : product.id;
                let qty = box ? box.qty : product.qty;
                let currentLocationID = this.linesWidget.scannedLocationID;
                if (currentLocationID) {
                    // Check product if having any ready move lines
                    let moveLines = this.datas[currentLocationID].move_lines;
                    moveLine = _.find(moveLines, function (line) {
                        return line.product.id == productID && Math.abs(line.reserved_qty - line.qty_done) > EPSILON
                    });
                    if (moveLine != undefined) {
                        this.scannedQty = qty;
                    }
                }
            }

            return moveLine
        },
        
        _isProductInLocation: function(barcode){
            let moveLine = undefined;
            let product = this.barcodetoProduct[barcode];
            let box = this.barcodetoBox[barcode];
            if (product || box) {
                let productID = box ? box.product_id : product.id;
                let currentLocationID = this.linesWidget.scannedLocationID;
                if (currentLocationID) {
                    // Check product if having any ready move lines
                    let moveLines = this.datas[currentLocationID].move_lines;
                    moveLine = _.find(moveLines, function (line) {
                        return line.product.id == productID
                    });
                }
            }

            return moveLine
        },

        _isTrackingProduct: function (productID) {
            return this.productSettings[productID].tracking;
        },

        _isFinishedLocation: function (ev) {
            let moveLines = this.datas[ev.data.locationID].move_lines  ;
            let isNotFinish = _.find(moveLines, function (e) {
                return Math.abs(e.reserved_qty - e.qty_done) > EPSILON;
            });
            if (!isNotFinish) {
                this.linesWidget._onClickNextLocation();
            }
            return !isNotFinish;
        },

        _isFullyReserved: function (highlight = true) {
            let self = this;
            let isFully = this.locations.every(function (location, index) {
                let moveLines = self.datas[location.id].move_lines;
                let isNotFully = _.find(moveLines, function (e) {
                    return Math.abs(e.reserved_qty - e.qty_done) > EPSILON;
                });
                return !isNotFully;
            });
            if (highlight) {
                this.trigger_up('toggle_button', {btnClass: '.o_validate', primary: isFully});
            }

            return isFully;
        },

        _isReservedLocation: function (locationID) {
            let moveLines = this.datas[locationID].move_lines;

            let isNotFully = _.find(moveLines, function (e) {
                return Math.abs(e.reserved_qty - e.qty_done) > EPSILON;
            });
            return !isNotFully
        },

        _step_serial_number: function (barcode, linesActions) {
            let productID = this.linesWidget.scannedProductID;
            let currentLocationID = this.linesWidget.scannedLocationID;
            let serialNumber = undefined;
            if (this._isTrackingProduct(productID) != 'serial'){
                return Promise.reject(_t("This product is not tracking by serial number."));
            }
            if (productID) {
                let scannedSerialNumbers = this.scannedSerialNumbers[productID] || [];
                serialNumber = _.find(this.productSettings[productID].serials_lots,
                    function (e) {
                        return e.name == barcode
                    });
                if (serialNumber && scannedSerialNumbers.length > 0) {
                    let scannedLot = _.find(scannedSerialNumbers, function (e) {
                        return e == serialNumber.id
                    });
                    if (scannedLot) {
                        let errorMessage = _t("This serial number has been picked. Please scan a new serial number.");
                        this.do_warn(_t("Error"), errorMessage);
                        return Promise.resolve({linesActions: linesActions});
                    }
                }
            }

            if (serialNumber) {
                let foundSerial = _.find(this.serialsLots,
                    function (e) {
                        return e.id == serialNumber.id
                    });
                if (currentLocationID != foundSerial.location) {
                    this.do_warn(_t("Error"), _t("This serial number does not belong to the selected location."));
                    return Promise.resolve({linesActions: linesActions});
                }
                this.scannedQty = 1;
                this.linesWidget._updateScannedSerialNumber(serialNumber);
                this.currentStep = 'tote_bin';
                return Promise.resolve({linesActions: linesActions});
            } else {
                serialNumber = _.find(this.serialsLots,
                    function (e) {
                        return e.name == barcode
                    });
                if (serialNumber) {
                    this.do_warn(_t("Error"), _t("This serial number does not belong to the selected product."));
                    return Promise.resolve({linesActions: linesActions});
                } else {
                    let errorMessage = _t("You are expected to scan a serial number");
                    return this._step_product(barcode, linesActions, true).then(function (res) {
                        if (res) return Promise.resolve({linesActions: res.linesActions});
                    }, function () {
                        return Promise.reject(errorMessage);
                    });
                }
            }
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
            let moveLine = this._findMoveLine(barcode);
            if (moveLine) {
                this.scannedMoveLine = moveLine;
                let productID = moveLine.product.id;
                this.linesWidget._recommendMoveLine(moveLine.move_line_id);
                this.linesWidget._updateScannedProductID(productID);
                // Get qty from barcode of product
                if (this._isTrackingProduct(productID) == 'serial') {
                    this.currentStep = 'serial_number';
                } else {
                    this.currentStep = 'tote_bin';
                }
            } else {
                if (this._isProductExisted(barcode)){
                    let errorMessage = _t("This product has been fully picked. Please scan another one.");
                    if (!this._isProductInLocation(barcode)){
                        errorMessage = _t("This product does not belong to selected location. Please scan a new product.");
                    }

                    return Promise.reject(errorMessage);
                }
                let self = this;
                let errorMessage = _t("You are expected to scan a valid product.");
                return self._step_location(barcode, linesActions).then(function (res) {
                    return Promise.resolve({linesActions: res.linesActions});
                }, function () {
                    return Promise.reject(errorMessage);
                });
            }

            return Promise.resolve({linesActions: linesActions});
        },

        _onReset: function (ev) {
            let self = this;
            ev.stopPropagation();

            let locationID = ev.data.locationID;
            let moveLineID = ev.data.moveLineID;
            let productID = ev.data.productID;
            let $line = ev.data.element;

            Dialog.confirm(this, (_t("This action will clear quantity of this item. Do you want to continue ?")), {
                confirm_callback: () => {
                    self.linesWidget._resetQuantity($line, moveLineID, locationID, productID);
                },
            });
        },

        _onUpdateScannedSerialNumbers: function (ev) {
            if (ev.data.add == true) {
                this.scannedSerialNumbers[ev.data.productID] = this.scannedSerialNumbers[ev.data.productID] || [];
                this.scannedSerialNumbers[ev.data.productID].push(ev.data.serialNumberID);
            } else if (ev.data.remove == true) {
                let index = _.indexOf(this.scannedSerialNumbers[ev.data.productID], ev.data.serialNumberID);
                if (index != undefined) {
                    this.scannedSerialNumbers[ev.data.productID].splice(index, 1)
                }
            }
        },

        _onValidate: function () {
            let self = this;

            if (this._isFullyReserved()) {
                this._rpc({
                    model: 'stock.picking.batch',
                    method: 'action_done',
                    args: [[parseInt(this.waveID)]]
                }).then(function(){
                    self.do_notify(_t("Success"), _t("Validate successfully."));
                    self.trigger_up('exit', {noConfirm: true});
                })

            } else {
                let dialog = new Dialog(this, {
                    title: _t('Confirmation'),
                    size: 'medium',
                    $content: QWeb.render('wave_barcode_confirmation', {
                        'message': _t("Orders have not been fully picked. Do you want to validate ?")
                    }),
                    buttons: [
                        {text: _t('Yes'), click: function () {
                            self._rpc({
                                model: 'stock.picking.batch',
                                method: 'force_validate',
                                args: [[parseInt(self.waveID)], false, false],
                            }).then(function (res) {
                                if (res.success == true) {
                                    if (res.not_done_moves_data) {
                                        let groups = _.groupBy(res.not_done_moves_data, function (m) {
                                            return m.origin
                                        });
                                        let datas = _.map(groups, function (value, key) {
                                            return {title: key, lines: value}
                                        });
                                        self.linesWidget.destroy();
                                        self.is_not_fully_pickied_screen = true;
                                        new RemainingLinesWidget(self, 'Orders have not been fully picked', datas).appendTo(self.$('.o_content'));
                                    }
                                }else{
                                    self.do_warn(_t("Error"), _t("Something went wrong while validating this wave."));
                                }
                            }).guardedCatch(function () {
                                self.do_warn(_t("Error"), _t("Something went wrong while validating this wave."));

                            });
                            dialog.close();
                        }, classes: 'btn-primary'
                    },
                    {text: _t('No'), close: true}
                ]}).open();
            }
        },

        _onToggleDisableButton: function(ev){
            ev.stopPropagation();
            let btnClass = ev.data.btnClass;
            let isDisable = ev.data.isDisable;
            let $electedBtn = this.$(btnClass);
            $electedBtn.attr('disabled', isDisable);
        },

        _onToggleButton: function(ev){
            ev.stopPropagation();
            let btnClass = ev.data.btnClass;
            let primary = ev.data.primary;
            let $electedBtn = this.$(btnClass);
            $electedBtn.toggleClass('btn-secondary', !primary);
            $electedBtn.toggleClass('btn-primary', primary);
        },

        _onEditLine: function (ev) {
            let moveLineID = ev.data.moveLineID;
            let qtyDone = ev.data.qtyDone;
            let reservedQty = ev.data.reservedQty;
            let locationID = ev.data.locationID;
            let productName = ev.data.productName;
            let uom = ev.data.uom;
            this.linesWidget.destroy();
            let data = {
                locationID: locationID,
                moveLineID: moveLineID,
                productName: productName,
                qtyDone: qtyDone,
                reservedQty: reservedQty,
                uom: uom,}
            new EditLineWidget(this, data, 'stock.move.line', moveLineID).appendTo(this.$('.o_content'));
        }
    })

    core.action_registry.add('order_wave_picking_barcode_client_action', OrderWavePickingClientAction);

    return OrderWavePickingClientAction;
});
