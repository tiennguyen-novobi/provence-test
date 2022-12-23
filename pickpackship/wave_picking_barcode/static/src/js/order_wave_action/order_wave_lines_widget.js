odoo.define('wave_picking_barcode.OrderWaveLinesWidget', function (require) {
    'use strict';

    const EPSILON = 0.00001;
    var core = require('web.core');
    var SendAlertDialog = require('wave_picking_barcode.send_alert_dialog');
    var QWeb = core.qweb;
    var LinesWidget = require('wave_picking_barcode.WaveLinesWidget');
    var _t = core._t;

    var OrderWaveLinesWidget = LinesWidget.extend({
        template: 'order_wave_picking_lines_widget',
        events : {
            'click .o_validate': '_onClickValidate',
            'click .o_send_alert': '_onClickSendAlert',
            'click .o_previous_location': '_onClickPreviousLocation',
            'click .o_next_location': '_onClickNextLocation',
            'click .o_reset': '_onClickReset',
            'click .o_edit': '_onClickEdit',
            "change input[name='qty_done']": 'onChangeQtyDone'
        },

        init: function (parent, data={}) {
            this._super.apply(this, arguments);
            this.parent = parent;
            this.datas = parent.datas;
            this.lines = _.values(this.datas);
            this.warehouse = parent.warehouse;
            this.locations = parent.locations;
            this.productSettings = parent.productSettings;
            this.scannedLocationID = undefined;
            this.currentLocationID = data.locationID || this.locations[0].id;
            this.scannedProductID = undefined;
            this.$location = undefined;
            this.scannedSerialNumber = undefined;
            this.qty_done = undefined;
        },

        start: function () {
            var self = this;
            return this._super.apply(this, arguments).then(function () {
                return self._renderLines();
            });
        },

        _renderLines: function () {
            var $body = this.$el.filter('.o_barcode_lines');

            var $content = $(QWeb.render('order_wave_picking_lines', {
                'orderToteBins': this.parent.orderToteBins,
                'datas': this.datas,
                'locations': this.locations}));
            this._toggleScanMessage('scan_location');
            $body.empty().append($content);
            this.trigger_up('check_done');

            if (this.scannedLocationID){
                this._updateScannedLocationID(this.scannedLocationID);

            } else if (this.currentLocationID){
                this._updateCurrentLocationID(this.currentLocationID);
            }
        },

        _updateCurrentLocationID: function(locationID){
            if (this.scannedLocationID){
                this.scannedLocationID = undefined;
                this.parent.currentStep = 'location';
                this.$location = undefined;
                this._toggleScanMessage('scan_location');
                this.$('.highlight_location').toggleClass('highlight_location', false);
                this.clearLineHighlight();
                this.trigger_up('toggle_disable_button', {btnClass: '.o_send_alert', isDisable: true});
            }

            this.currentLocationID = locationID;
            this.$locationEle = this.$el.find(".o_barcode_location[data-location-id='" + locationID.toString() + "']");
            this._onlyShowLine(this.$locationEle);
            
            this.trigger_up('toggle_disable_button', {btnClass: '.o_next_location', isDisable: false});
            this.trigger_up('toggle_disable_button', {btnClass: '.o_previous_location', isDisable: false});
        },

        _updateScannedLocationID: function(locationID){
            this._updateCurrentLocationID(locationID);

            this.scannedLocationID = locationID;
            this._toggleScanMessage('scan_product');
            this.$('.highlight_location').toggleClass('highlight_location', false);
            this.$location = this.$el.find(".o_barcode_location[data-location-id='" + locationID.toString() + "']");
            this.$location.find('.o_barcode_lines_header').toggleClass('highlight_location', true);
            this.trigger_up('toggle_disable_button', {btnClass: '.o_send_alert', isDisable: false})
        },

        _updateScannedProductID: function(productID, hasSerialNumber, hasLotNumber){
            this.scannedProductID = productID;
            if (this.productSettings[productID].tracking == 'serial' && !hasSerialNumber){
                this._toggleScanMessage('scan_serial');
            }else if (this.productSettings[productID].tracking == 'lot' && !hasLotNumber){
                this._toggleScanMessage('scan_lot');
            }else{
                this._toggleScanMessage('scan_bin');
            }
            this.parent.do_notify(_t("Success"),  _t("Scan product successfully"));
        },

        _updateScannedSerialNumber: function(serialNumber){
            this.scannedSerialNumber = serialNumber;
            this._toggleScanMessage('scan_bin');
            this.parent.do_notify(_t("Success"),  _t("Scan serial number successfully"));
        },

        _recommendMoveLine: function(moveLineID){
            let input = undefined;
            if (this.$location) {
                let $inputs = this.$location.find("input[name='qty_done']");
                input = _.find($inputs, function (input) {
                    return $(input).data('move-line-id') == moveLineID
                });
            }
            let $line = $(input).parents('.o_barcode_line');
            this._highlightLine($line);
        },

        onChangeQtyDone: function(ev){
            let self = this;
            let $input = $(ev.currentTarget);
            let reserved_qty = $input.data('reserved-qty');
            let moveLineID = $input.data('move-line-id');
            let productID = $input.data('product-id');
            let locationID = parseInt($input.closest(".o_barcode_location").data('location-id'));
            this._updateScannedLocationID(locationID);
            this._updateScannedProductID(productID);
            if (isNaN($input.val())){
                this.parent.do_warn("The entered quantity must be a number.")
                $input.val(0);
            }

            let current_qty_done = parseFloat($input.val());
            if (current_qty_done < 0){
                this.parent.do_warn("The entered quantity must be a non-negative integer.")
                current_qty_done = 0;
            }
            else if(current_qty_done - reserved_qty > EPSILON){
                this.parent.do_warn("The entered quantity must be equal or less than the expected quantity.")
                current_qty_done = reserved_qty;
            }

            let lines = this.datas[this.scannedLocationID].move_lines;
            let line = _.find(lines, function(e){
                return e.move_line_id == moveLineID
            });

            let lotID = false;
            $input.val(current_qty_done);
            return this._rpc({
                model: 'stock.move.line',
                method: 'update_scanning_qty',
                args: [[parseInt(moveLineID)], this.scannedLocationID, current_qty_done, lotID],
            }).then(function (res) {
                self._updateScannedLocationID(locationID);
                self.scannedProductID = undefined;
                self.parent.currentStep = 'product';

                line.qty_done = res.qty_done;
                line.lot_name = res.lot_name;
                line.move_line_id = res.id;
                self._renderMoveline($input, line);
                self._highlightLine($input);
                self.trigger_up('check_done');
                if (res.lot_id){
                    self.trigger_up('update_scanned_serial_numbers', {
                        add: true, productID: productID, serialNumberID: res.lot_id});
                }
            })
        },

        incrementProduct: function(moveLineID, qty){
            let self = this;
            if (this.scannedProductID){
                return this._incrementProduct(moveLineID, this.scannedProductID, qty, this.scannedSerialNumber).then(function(){
                    self.scannedProductID = undefined;
                    self.scannedSerialNumber = undefined;
                    self._toggleScanMessage('scan_more');
                });
            }
            return Promise.reject();
        },

        _getInputCandidate: function(moveLineID){
            let input = undefined;
            if (this.$location) {
                let $inputs = this.$location.find("input[name='qty_done']");
                input = _.find($inputs, function (input) {
                    return $(input).data('move-line-id') == moveLineID
                });
            }
            return input
        },

        _incrementProduct: function(moveLineID, productID, qty, lot){
            let self = this;
            let input = this._getInputCandidate(moveLineID);

            let lines = this.datas[this.scannedLocationID].move_lines;
            let line = _.find(lines, function(e){
                return e.move_line_id == moveLineID
            });
            let qty_done = line.qty_done + qty;

            let lotID = false;

            if (lot){
                lotID = lot.id;
            }

            return this._rpc({
                model: 'stock.move.line',
                method: 'update_scanning_qty',
                args: [[parseInt(moveLineID)], this.scannedLocationID, qty_done, lotID],
            }).then(function (res) {
                line.qty_done = res.qty_done;
                line.lot_name = res.lot_name;
                line.move_line_id = res.id;
                let $line = $(input).parents('.o_barcode_line');
                self._renderMoveline($line, line);
                self._highlightLine($line);
                self.trigger_up('check_done');
                self.trigger_up('check_finished_location', {'locationID': self.scannedLocationID});
                if (res.lot_id){
                    self.trigger_up('update_scanned_serial_numbers', {
                        add: true, productID: productID, serialNumberID: res.lot_id});
                }
            })
        },

        _resetQuantity: function($line, moveLineID, locationID, productID, lot) {
            let self = this;

            let lines = this.datas[locationID].move_lines;
            let line = _.find(lines, function(e){
                return e.move_line_id == moveLineID
            });

            this._rpc({
                model: 'stock.move.line',
                method: 'update_scanning_qty',
                args: [[parseInt(moveLineID)], locationID, 0],
            }).then(function (res) {
                line.qty_done = res.qty_done;
                line.lot_name = res.lot_name;
                line.move_line_id = res.id;
                let lotID = res.lot_id;
                if (lotID && self.parent.scannedSerialNumbers[productID]){
                    self.trigger_up('update_scanned_serial_numbers', {remove: true, productID: productID, serialNumberID: lotID});
                }
                self._renderMoveline($line, line)
            })
        },

        _renderMoveline: function($line, lineData){
            $line.empty().append($(QWeb.render('order_wave_picking.move_line',
                {'line': lineData, 'orderToteBins': this.parent.orderToteBins})));
        },

        _getNextLocationID: function (locationID){
            let currentLocationIndex = _.findIndex(this.locations, function(location){ return location.id == locationID});
            let nextLocation = currentLocationIndex + 1;
            if (nextLocation >= this.locations.length){
                nextLocation = 0;
            }
            nextLocation = this.locations[nextLocation].id;
            return nextLocation;
        },

        _getPreviousLocationID: function (locationID){
            let currentLocationIndex = _.findIndex(this.locations, function(location){ return location.id == locationID});
            let previousLocation = currentLocationIndex - 1;
            if (previousLocation < 0){
                previousLocation = this.locations.length - 1;
            }
            previousLocation = this.locations[previousLocation].id;
            return previousLocation;
        },

        _onClickNextLocation: function(ev){
            let nextLocationID = this._getNextLocationID(this.currentLocationID);
            if (nextLocationID === undefined){
               this.parent.do_warn("This is the last location.");
            }
            else{
                this._updateCurrentLocationID(nextLocationID);
            }
        },

        _onClickPreviousLocation: function (ev) {
            let previousLocationID = this._getPreviousLocationID(this.currentLocationID);
            if (previousLocationID === undefined) {
                this.parent.do_warn("This is the first location.");
            } else {
                this._updateCurrentLocationID(previousLocationID);
            }
        },

        _onClickValidate: function(ev){
            this.trigger_up('validate');
        },

        _onClickReset: function (ev) {
            let $line = $(ev.currentTarget).closest('.o_barcode_line');
            let locationID = $(ev.currentTarget).closest('.o_barcode_location').data('location-id');
            let moveLineID = $(ev.currentTarget).data('move-line-id');
            let productID = $(ev.currentTarget).data('product-id');
            this.trigger_up('reset', {locationID: locationID, moveLineID: moveLineID, productID: productID, element: $line});
        },

        _onClickSendAlert: function(ev){
            let self = this;
            let location = _.find(this.locations, function(location){ return location.id == self.scannedLocationID});
            var data = {
                'location': location,
                'warehouse': this.warehouse
            }

            let sendAlertDialog = new SendAlertDialog(this, data);
            sendAlertDialog.open();
        },

        _onClickEdit: function(ev){
            let locationID = $(ev.currentTarget).data('location-id');
            let moveLineID = $(ev.currentTarget).data('move-line-id');
            let qtyDone = $(ev.currentTarget).data('qty-done');
            let reservedQty = $(ev.currentTarget).data('reserved-qty');
            let productName = $(ev.currentTarget).data('product-name');
            let uom = $(ev.currentTarget).data('uom');
            this.trigger_up('edit_line', {locationID: locationID, moveLineID: moveLineID,
                qtyDone: qtyDone, reservedQty: reservedQty, productName: productName, uom: uom});
        }


    })
    return OrderWaveLinesWidget
})