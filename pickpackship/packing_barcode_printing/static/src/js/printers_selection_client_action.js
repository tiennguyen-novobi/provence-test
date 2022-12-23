/** @odoo-module **/

import core from 'web.core';
import AbstractAction from 'wave_picking_barcode.abstract_action_extend';
import SoundsWidget from 'wave_picking_barcode.SoundsWidget';

const { Component } = owl;
const { useState, useRef } = owl.hooks;

class PrintersSelectionActionButtons extends Component {
    constructor(parent, props) {
        super(parent, props);
        this.parent = parent;
    }

    onConfirm(ev) {
        this.parent.onConfirm();
    }

    onClose(ev) {
        this.parent.onClose();
    }

    mounted() {
        super.mounted(...arguments);
        $(document.body.getElementsByClassName('modal-footer')[0]).append($(this.el))
    }
}
PrintersSelectionActionButtons.template = "ButtonPrintersSelection";


class PrintersSelectionContent extends Component {
    constructor(parent, props) {
        super(null, props);
        this.parentWidget = parent;
        this.props = props || {};

        this.state = useState({
            selectedIoTDeviceID: null,
        });

        //Set default printer to this.state.selectedIoTDeviceID
        let printer = _.find(this.props.printers, function (p) {
            return p.is_default;
        });
        if (printer) {
            this.state.selectedIoTDeviceID = printer.id;
        }
        this.default_device = useRef("default_device_valid");
    }

    onConfirm(ev) {
        if (this.state.selectedIoTDeviceID == null) {
            this.parentWidget.do_warn('Please select device!');
            return Promise.reject('Missing selected device');
        }
        this.parentWidget.onConfirm(this.state.selectedIoTDeviceID, this.state.copies, this.state.selectedRecordID);
    }

    onClose(ev) {
        this.parentWidget.onClose();
    }

    mounted() {
        super.mounted(...arguments);
        if (this.default_device.el) {
            this.default_device.el.click();
        }
    }

}
PrintersSelectionContent.template = 'PrintersSelectionContentContent';
PrintersSelectionContent.components = {PrintersSelectionActionButtons};


const PrintersSelectionAction = AbstractAction.extend({
    contentTemplate: "packing_barcode_printing.PrintersSelectionAction",

    init: function (parent, options) {
        this._super.apply(this, arguments);
        this.printingServerActionID = options.params.printing_server_action_id;
        this.printFile = options.context.print_file;
        this.labels = options.context.labels;
        this.printing_service = options.context?.printing_service;
        this.printers = (options.context?.printers) ? options.context?.printers : [];
    },

    start() {
        let self = this;
        this.soundsWidget = new SoundsWidget(this);
        this._super.apply(this, arguments).then(function () {
            self.soundsWidget.prependTo(self.$('.o_content'));
            self.container = self.el.getElementsByClassName("o_printers_selection_action")[0];

            let printers = self.printers;
            if (Array.isArray(printers) && printers.length !== 0){
                self._updatePrinters(printers)
            }
        })
    },

    _updatePrinters(printers) {
        this.content = new PrintersSelectionContent(this, {printers: printers});
        this.content.mount(this.container);
    },

    _updateDefaultPrinter(printerID) {
        let self = this;
        this._rpc({
            model: 'iot.device',
            method: 'update_default_printer',
            args: [[], self.printingServerActionID, printerID]
        })
    },

    onClose() {
        this.do_action({type: 'ir.actions.act_window_close'});
    },

    onConfirm: function (deviceID) {
        this._updateDefaultPrinter(deviceID);
        let printer = _.find(this.printers, function (printer) {
            return printer.id == parseInt(deviceID)
        });

        return this.do_action('packing_barcode.packing_barcode_client_action', {
            additional_context: {
                printer: printer,
                printing_service: this.printing_service,
            },
        })
    },

});

core.action_registry.add('printers_selection_client_action', PrintersSelectionAction);

export default PrintersSelectionAction;
