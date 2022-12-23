odoo.define('wave_picking_barcode.RemainingLinesWidget', function (require) {
    'use strict';

    var Widget = require('web.Widget');
    var core = require('web.core');
    var QWeb = core.qweb;

    var RemainingLinesWidget = Widget.extend({
        template: 'remaining_lines_widget',
        events : {
            'click .o_close': '_onClickClose',
        },

        init: function (parent, title, groups) {
            this._super.apply(this, arguments);
            this.parent = parent;
            this.title = title;
            this.groups = groups
        },

        start: function () {
            var self = this;
            return this._super.apply(this, arguments).then(function () {
                return self._renderLines();
            });
        },

        _renderLines: function () {
            var $body = this.$el.filter('.o_barcode_lines');
            var $content = $(QWeb.render('remaining_lines', {'groups': this.groups}));
            $body.empty().append($content);
        },

        _onClickClose: function(){
            this.parent.is_not_fully_pickied_screen = false;
            if (this.parent.wave_type == 'tote'){
                this.trigger_up('scan_wave_label');
                this.destroy();
            }else{
                this.trigger_up('exit', {noConfirm: true});
            }
        }

    })
    return RemainingLinesWidget
})