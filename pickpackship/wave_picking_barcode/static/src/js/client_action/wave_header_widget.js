odoo.define('wave_picking_barcode.WaveHeaderWidget', function (require) {
'use strict';

let Widget = require('web.Widget')

let WaveHeaderWidget = Widget.extend({
    'template': 'stock_barcode_header_widget',
    events: {
        'click .o_exit': '_onClickExit',
        'click .o_show_information': '_onClickShowInformation',
        'click .o_show_settings': '_onClickShowSettings',
        'click .o_close': '_onClickClose',
    },

    init: function (parent) {
        this._super.apply(this, arguments);
        this.title = parent.title;
    },

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    /**
     * Toggle the header between two display modes: `init` and `specialized`.
     * - in init mode: exit, informations and settings button are displayed;
     * - in specialized mode: close button is displayed twice with not necessarily
     *   the same icon to better suit what users might expect for navigation.
     *
     * @param {string} mode: "init" or "settings".
     */
    toggleDisplayContext: function (mode) {
        var $showInformation = this.$('.o_show_information');
        var $showSettings = this.$('.o_show_settings');
        var $close = this.$('.o_close');
        var $exit = this.$('.o_exit');

        if (mode === 'init') {
            $showInformation.toggleClass('o_hidden', false);
            $showSettings.toggleClass('o_hidden', false);
            $close.toggleClass('o_hidden', true);
            $exit.toggleClass('o_hidden', false);
        } else if (mode === 'specialized') {
            $showInformation.toggleClass('o_hidden', true);
            $showSettings.toggleClass('o_hidden', true);
            $close.toggleClass('o_hidden', false);
            $exit.toggleClass('o_hidden', true);
        }
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * Handles the click on the `exit button`.
     *
     * @private
     * @param {MouseEvent} ev
     */
    _onClickExit: function (ev) {
        ev.stopPropagation();
        this.trigger_up('exit');
    },

    /**
     * Handles the click on the `settings button`.
     *
     * @private
     * @param {MouseEvent} ev
     */
     _onClickShowInformation: function (ev) {
        ev.stopPropagation();
        this.trigger_up('show_information');
    },

    /**
     * Handles the click on the `settings button`.
     *
     * @private
     * @param {MouseEvent} ev
     */
     _onClickShowSettings: function (ev) {
        ev.stopPropagation();
        this.trigger_up('show_settings');
    },

    /**
     * Handles the click on the `close button`.
     *
     * @private
     * @param {MouseEvent} ev
     */
     _onClickClose: function (ev) {
        ev.stopPropagation();
        this.trigger_up('reload');
    },

    _reloadTitle: function (title) {
        this.title = title;
        let $title_el = this.$el.find('.o_title');
        $title_el.replaceWith("<span class=\"o_title navbar-text text-white\">" + this.title + "</t></span>");
    },

});

return WaveHeaderWidget;

});
