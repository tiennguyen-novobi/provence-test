odoo.define('wave_picking_barcode.WaveLinesWidget', function (require) {
    'use strict';

    var Widget = require('web.Widget');

    var WaveLinesWidget = Widget.extend({
        _toggleScanMessage: function (message) {
            this.$('.o_scan_message').toggleClass('o_hidden', true);
            this.$('.o_scan_message_' + message).toggleClass('o_hidden', false);
        },

        hideAllLine: function () {
            var $body = this.$el.find('.o_barcode_location');
            // Hide all lines
            $body.addClass('o_hidden');
        },

        _onlyShowLine: function ($line) {
            this.hideAllLine();
            // Show `$line`.
            $line.removeClass('o_hidden');
        },

        clearLineHighlight: function () {
            var $body = this.$el.filter('.o_barcode_lines');
            // Remove the highlight from the other line.
            $body.find('.o_highlight').removeClass('o_highlight');
            $body.find('.o_highlight_green').removeClass('o_highlight_green');
        },

        _highlightLine: function ($line, doNotClearLineHighlight) {
            var $body = this.$el.filter('.o_barcode_lines');
            if (! doNotClearLineHighlight) {
                this.clearLineHighlight();
            }
            // Highlight `$line`.
            $line.toggleClass('o_highlight', true);
            $line.parents('.o_barcode_lines').toggleClass('o_js_has_highlight', true);
            $line.toggleClass('o_highlight_green', true);

            // Scroll to `$line`.
            $body.animate({
                scrollTop: $body.scrollTop() + $line.position().top - $body.height()/2 + $line.height()/2
            }, 500);
        },

    })
    return WaveLinesWidget
})