odoo.define('wave_picking_barcode.EditLineWidget', function (require) {
    'use strict';

    var Widget = require('web.Widget');
    var core = require('web.core');
    var _t = core._t;
    var QWeb = core.qweb;
    const EPSILON = 0.00001;

    var EditLineWidget = Widget.extend({
        template: 'edit_line_widget',
        events : {
            'click .o_discard': '_onReload',
            'click .o_confirm': '_onConfirm',
        },

        init: function (parent, data, model, resID) {
            this._super.apply(this, arguments);
            this.parent = parent;
            this.data = data;
            this.model = model;
            this.resID = resID;
        },

        start: function () {
            var self = this;
            return this._super.apply(this, arguments).then(function () {
                return self._renderLines();
            });
        },

        _renderLines: function () {
            var $body = this.$el.filter('.o_content');
            var $content = $(QWeb.render('edit_line_content', {'data': this.data}));
            $body.empty().append($content);
        },

        _onReload: function(){
            this.trigger_up('reload', {'locationID': this.data.locationID});
            this.destroy();
        },

        _onCheckQtyDone: function(){
            let $input =  this.$el.find("input[name='qty-done']");
            let reservedQty = this.data.reservedQty;

            if (isNaN($input.val())){
                this.parent.do_warn("The entered quantity must be a number.")
                $input.val(0);
                return false
            }

            let currentQtyDone = parseFloat($input.val());
            if (currentQtyDone < 0){
                this.parent.do_warn("The entered quantity must be a non-negative integer.");
                return false
            }
            else if(currentQtyDone - reservedQty > EPSILON){
                this.parent.do_warn("The entered quantity must be equal or less than the expected quantity.")
                return false
            }

            return true
        },

        _onConfirm: function(){
            let self = this;
            if(this._onCheckQtyDone()){
                let $input = this.$el.find("input[name='qty-done']")
                let currentQtyDone = parseFloat($input.val());
                if (this.model == 'stock.move.line'){
                    this._rpc({
                        model: this.model,
                        method: 'write',
                        args: [[parseInt(this.resID)], {qty_done: currentQtyDone}]
                    }).then(function(){
                        self.trigger_up('reload', {'locationID': self.data.locationID});
                        self.destroy();
                    })
                }else if (this.model == 'stock.picking.batch'){
                    currentQtyDone = parseFloat($input.val()) - parseFloat($input.data('qty-done'));
                    this._rpc({
                        model: this.model,
                        method: 'update_wave_picking',
                        args: [[parseInt(this.resID)], this.data.locationID, this.data.productID, currentQtyDone]
                    }).then(function(res){
                        if (res){
                            self.trigger_up('reload', {'locationID': self.data.locationID});
                            self.destroy();
                        }else{
                            self.parent.do_warn(_t("Error"), _t("Something went wrong while updating. Please try again!"));
                        }
                    })
                }

            }

        }

    })
    return EditLineWidget
})