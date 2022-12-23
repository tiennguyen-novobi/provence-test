/** @odoo-module **/

import MainMenu from "@stock_barcode/stock_barcode_menu";

MainMenu.include({
    events: _.extend({}, MainMenu.prototype.events, {
        "click .button_packing": function () {
            this.do_action('packing_barcode.packing_barcode_client_action');
        },
    }),
})