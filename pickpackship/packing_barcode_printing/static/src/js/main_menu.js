/** @odoo-module **/

import MainMenu from "@stock_barcode/stock_barcode_menu";

MainMenu.include({
    events: _.extend({}, MainMenu.prototype.events, {
        "click .button_packing": function(){
            const self = this;
            this._rpc({
                model: "ir.config_parameter",
                method: "get_param",
                args: ["printing.service"],
            }).then(function (printing_service) {
                if (printing_service == 'iot') {
                    self._rpc({
                        model: 'iot.device',
                        method: 'get_printers',
                        args: [[], self.printingServerActionID]
                    }).then(function (printers) {
                        if (Array.isArray(printers) && printers.length !== 0){
                            return self.do_action('packing_barcode_printing.printers_selection_client_action', {
                                'additional_context': {
                                    'printing_service': printing_service,
                                    'printers': printers
                                }
                            });
                        }
                        else{
                            return self.do_action('packing_barcode.packing_barcode_client_action');
                        }
                    });
                }
                else{
                    return self.do_action('packing_barcode.packing_barcode_client_action');
                }
            });
        },
    }),
})