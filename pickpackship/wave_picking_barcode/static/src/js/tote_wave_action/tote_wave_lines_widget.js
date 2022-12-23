odoo.define('wave_picking_barcode.ToteWaveLinesWidget', function (require) {
    'use strict';

    const EPSILON = 0.00001;
    var core = require('web.core');
    var SendAlertDialog = require('wave_picking_barcode.send_alert_dialog');
    var QWeb = core.qweb;
    var LinesWidget = require('wave_picking_barcode.WaveLinesWidget');

    var ToteWaveLinesWidget = LinesWidget.extend({
        template: 'tote_wave_picking_lines_widget',
        events : {
            'click .o_validate': '_onClickValidate',
            'click .o_partially_validate': '_onClickPartiallyValidate',
            'click .o_send_alert': '_onClickSendAlert',
            'click .o_previous_location': '_onClickPreviousLocation',
            'click .o_next_location': '_onClickNextLocation',
            'click .o_edit': '_onClickEdit',
            "change input[name='qty_done']": 'onChangeQtyDone'
        },

        init: function (parent, data= {}) {
            this._super.apply(this, arguments);
            this.parent = parent;
            this.datas = parent.datas;
            this.warehouse = parent.warehouse;
            this.locations = parent.locations;
            this.productSettings = parent.productSettings;
            this.qty_done = {};
            this.scannedLocationID = undefined;
            this.currentLocationID = data.locationID || this.locations[0].id;
            this.$location = undefined;
        },

        start: function () {
            var self = this;
            return this._super.apply(this, arguments).then(function () {
                return self._renderLines();
            });
        },

        _renderLines: function () {
            var $body = this.$el.filter('.o_barcode_lines');
            var $lines = $(QWeb.render('tote_wave_picking_lines', {
                'datas': this.datas,
                'locations': this.locations}));
            this._toggleScanMessage('scan_location');
            $body.empty().append($lines);
            this.trigger_up('check_done');

            if (this.currentLocationID){
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

        _getInputCandidate: function(productID){
            let input = undefined;
            if (this.$location) {
                let $inputs = this.$location.find("input[name='qty_done']");
                input = _.find($inputs, function (input) {
                    return $(input).data('product-id') == productID
                });
            }
            return input
        },

        onChangeQtyDone: function(ev){
            let $input = $(ev.currentTarget);
            let demand_qty = $input.data('demand-qty');
            let qty_done = $input.data('qty-done');
            let productID = $input.data('product-id');
            let locationID = parseInt($input.closest(".o_barcode_location").data('location-id'));
            this._updateScannedLocationID(locationID);
            if (isNaN($input.val())){
                this.parent.do_warn("The entered quantity must be a number.")
                $input.val(0);
            }

            let current_qty_done = parseFloat($input.val());
            if (current_qty_done < 0){
                this.parent.do_warn("The entered quantity must be a non-negative integer.")
                current_qty_done = 0;
            }
            else if(current_qty_done - demand_qty > EPSILON){
                this.parent.do_warn("The entered quantity must be equal or less than the expected quantity.")
                current_qty_done = demand_qty;
            }

            $input.val(current_qty_done);
            qty_done = current_qty_done - qty_done;
            let $line = $input.closest('.o_barcode_line');
            this.trigger_up('update_qty_done', {
                locationID: locationID,
                productID: productID,
                qty: qty_done,
                domElement: $line
            });
        },

        incrementProduct: function(productID, qty){
            let input = this._getInputCandidate(productID);
            if (input) {
                let $line = $(input).parents('.o_barcode_line');
                this.trigger_up('update_qty_done', {
                    locationID: this.scannedLocationID,
                    productID: productID,
                    qty: qty,
                    domElement: $line
                });
            }
        },

        reloadLine: function($line, lineData){
            $line.empty().append($(QWeb.render('tote_wave_picking_line', {'line': lineData})));
            this._highlightLine($line);
            this._toggleScanMessage('scan_more');
            this.trigger_up('check_finished_location', {'locationID': lineData.location_id})
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
            this.trigger_up('validate', {createNewWave: false});
        },

        _onClickPartiallyValidate: function(ev){
            this.trigger_up('partially_validate', {createNewWave: true});
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
            let qtyDone = $(ev.currentTarget).data('qty-done');
            let reservedQty = $(ev.currentTarget).data('reserved-qty');
            let productName = $(ev.currentTarget).data('product-name');
            let productID = $(ev.currentTarget).data('product-id');
            let uom = $(ev.currentTarget).data('uom');
            this.trigger_up('edit_line', {locationID: locationID, productID: productID,
                qtyDone: qtyDone, reservedQty: reservedQty, productName: productName, uom: uom});
        },

    })
    return ToteWaveLinesWidget
})