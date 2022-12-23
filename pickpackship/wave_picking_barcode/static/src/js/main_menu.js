/** @odoo-module **/

import MainMenu from "@stock_barcode/stock_barcode_menu";

MainMenu.include({
    events: _.extend({}, MainMenu.prototype.events, {
        "click .button_new_wave_picking": function(){
            this.do_action('wave_picking_barcode.action_wave_picking_creation');
        },
        "click .button_sorting_picking_barcode": function(){
            this.do_action('wave_picking_barcode.sorting_picking_barcode_client_action');
        }
    })
})
