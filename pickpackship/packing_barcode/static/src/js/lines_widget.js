odoo.define('packing_barcode.LinesWidget', function (require) {
    'use strict';

    var core = require('web.core');
    var Widget = require('web.Widget');
    var QWeb = core.qweb;

    var LinesWidget = Widget.extend({
        template: 'packing_lines_widget',
        events : {
            'click .o_validate': '_onClickValidate',
            'click .o_skip_packing': '_onSkipPacking',
            'click .o_print': '_onPrint'
        },

        init: function (parent, order, moveLines) {
            this._super.apply(this, arguments);
            this.parent = parent;
            this.order = order;
            this.moveLines = moveLines
        },

        start: function () {
            var self = this;
            return this._super.apply(this, arguments).then(function () {
                return self._renderLines();
            });
        },

        toggleButton: function(validate, print, skip){
            this.$el.find('.o_validate').toggleClass('o_hidden', validate);
            this.$el.find('.o_skip_packing').toggleClass('o_hidden', skip);
            this.$el.find('.o_print').toggleClass('o_hidden', print);
        },

        reload: function(data){
            this.order = data.order;
            this.moveLines = data.moveLines;
            this.bins = data.picking_bins;
            this._renderLines();
            this.toggleButton(false, false, false);
        },

        do_clean: function(){
            this.order = false;
            this.moveLines = false;
            this.bins = false;
            this.toggleButton(true, true, true);
            var $body = this.$el.filter('.o_barcode_lines');
            $body.empty();
        },

        _renderLines: function () {
            if (this.moveLines){
                var $body = this.$el.filter('.o_barcode_lines');
                var $lines = $(QWeb.render('packing_lines', {'widget': this}));
                $body.empty().append($lines);
            }

        },

        _onClickValidate: function(ev){
            this.trigger_up('validate');
        },

        _onSkipPacking: function(ev){
            this.trigger_up('skip_packing');
        },

        _onPrint: function(ev){
            this.trigger_up('print_label');
        }

    })
    return LinesWidget
})