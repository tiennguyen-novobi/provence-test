odoo.define('wave_picking_barcode.CreateWaveLabelWidget', function (require) {
    'use strict';

    var Widget = require('web.Widget');
    var core = require('web.core');
    var _t = core._t;
    var QWeb = core.qweb;

    var CreateWaveLabelWidget = Widget.extend({
        template: 'create_wave_label_widget',
        events : {
            'click .o_generate': '_onGenerate',
        },

        init: function (parent, new_wave_id) {
            this._super.apply(this, arguments);
            this.parent = parent;
            this.wave_label = undefined;
            this.new_wave_id = new_wave_id;
        },

        start: function () {
            var self = this;
            return this._super.apply(this, arguments).then(function () {
                return self._renderLines();
            });
        },

        _renderLines: function () {
            var $body = this.$el.filter('.o_barcode_lines');
            var $content = $(QWeb.render('create_wave_label_content', {'wave_label': this.wave_label}));
            $body.empty().append($content);
        },

        _updateWaveLabel: function (wave_label){
            this.wave_label = wave_label;
            var $button = this.$el.find('.o_generate');
            $button.toggleClass('o_hidden', false);
            this._renderLines();
        },

        _onGenerate: function (){
            if (this.wave_label){
                this.trigger_up('create_wave_label', {wave_label: this.wave_label, new_wave_id: this.new_wave_id})
            } else{
                this.parent.do_warn(_t("Error"), _t("Please scan a new batch label for this batch."));
            }

        }

    });
    return CreateWaveLabelWidget;
})