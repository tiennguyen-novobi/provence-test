odoo.define('wave_picking_barcode.SortingLinesWidget', function (require) {
    'use strict';

    var core = require('web.core');
    var _t = core._t;
    var Widget = require('web.Widget');
    var QWeb = core.qweb;
    var Dialog = require('web.Dialog');

    var SortingLinesWidget = Widget.extend({
        template: 'sorting_lines_widget',
        events : {
            'click .o_done_wave': '_onDoneWave',
            'click .o_undo_scan': '_onClickUndo',
        },

        init: function (parent, moveLine) {
            this._super.apply(this, arguments);
            this.parent = parent;
            this.moveLine = moveLine;
            this.stockMoveLineID = parent.stockMoveLineID;
            this.currentStep = parent.currentStep;
        },

        start: function () {
            var self = this;
            return this._super.apply(this, arguments).then(function () {
                self._toggleScanMessage('scan_' + self.currentStep);
            });
        },

        _renderLines: function () {
            this._toggleScanMessage('scan_' + this.currentStep);
            var $body = this.$el.filter('.o_barcode_lines');

            if (this.currentStep == 'wave_label'){
                $body.empty();
                this.$el.find('button.o_done_wave').toggleClass('o_hidden', true);
                this.$el.find('button.o_undo_scan').toggleClass('o_hidden', true);
            }else{
                this.$el.find('button.o_done_wave').toggleClass('o_hidden', false);
            }
            if (this.moveLine){
                if (this.parent.scannedBin != undefined){
                    this.$el.find('button.o_undo_scan').toggleClass('o_hidden', false);
                }else{
                    this.$el.find('button.o_undo_scan').toggleClass('o_hidden', true);
                }
                var $lines = $(QWeb.render('sorting_line', {'move_line': this.moveLine}));
                $body.empty().append($lines);
            }
        },

        _toggleScanMessage: function (message) {
            this.$('.o_scan_message').toggleClass('o_hidden', true);
            this.$('.o_scan_message_' + message).toggleClass('o_hidden', false);
        },

        incrementProduct: function(stockMoveLineID, qty, barcode){
            let input = this.$el.find("input[name='qty_done']");
            if (input) {
                let $line = $(input).parents('.o_barcode_line');
                this.trigger_up('update_qty_done', {
                    stockMoveLineID: stockMoveLineID,
                    qtyDone: qty,
                    toteBinBarcode: barcode,
                    domElement: $line
                });
            }
        },

        reload: function(moveLine, currentStep){
            this.moveLine = moveLine;
            this.currentStep = currentStep;
            this.stockMoveLineID = this.parent.stockMoveLineID;
            this._renderLines();
            if (!moveLine){
                this.$el.filter('.o_barcode_lines').empty();
                this.$el.find('button.o_done_wave').toggleClass('o_hidden', true);
                this.$el.find('button.o_undo_scan').toggleClass('o_hidden', true);
            }
        },

        _onDoneWave: function(ev){
            Dialog.confirm(this, _t("Do you want to complete sorting for the batch ?"), {
                confirm_callback: function () {
                    this.trigger_up('done_wave', {});
                },
            });
        },

        _onClickUndo: function(ev){
            Dialog.confirm(this, _t("Are you sure you want to undo the changes?"), {
                confirm_callback: function () {
                    this.trigger_up('reset_picking_bins', {});
                },
            });
        }

    })
    return SortingLinesWidget
})