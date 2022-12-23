odoo.define('printing_by_iot.IoTPrintingAction', function (require) {
    "use strict";

    let core = require('web.core');
    let AbstractAction = require('web.AbstractAction');
    let DeviceProxy = require('iot.DeviceProxy');
    const { Component } = owl;
    const { useState, useRef } = owl.hooks;

    var _t = core._t;

    class IoTPrintingActionButtons extends Component {
        constructor(parent, props) {
            super(parent, props);
            this.parent = parent;
        }
        onPrint(ev){
            this.parent.onPrint();
        }

        onClose(ev){
            this.parent.onClose();
        }

        mounted(){
            super.mounted(...arguments);
            $(document.body.getElementsByClassName('modal-footer')[0]).append($(this.el))
        }
    }

    IoTPrintingActionButtons.template = "ButtonIoTPrint";

    class IoTPrintingActionContent extends Component {

        constructor(parent, props) {
            super(null, props);
            this.parentWidget = parent;
            this.props = props || {};

            this.state = useState({
                selectedIoTDeviceID: null,
                copies : 1,
                selectedRecordID: null
            });

            //Set default printer to this.state.selectedIoTDeviceID
            let printer = _.find(this.props.printers, function (p){return p.is_default;});
            if (printer){
                this.state.selectedIoTDeviceID = printer.id;
            }
            this.default_device = useRef("default_device_valid");
        }

        onChangeSelectedRecord(ev){
            let selectedRecordID = parseInt($(ev.currentTarget).val());
            this.state.selectedRecordID = selectedRecordID;
            let selectedRecord = _.find(this.props.selectedRecords, function(selectedRecord){ return selectedRecord.id == selectedRecordID})
            this.state.copies = selectedRecord.default_copies;
        }

        onPrint(ev){
            if(this.props.selectedRecords && this.state.selectedRecordID == null){
                this.parentWidget.do_warn('Please select record!');
                return Promise.reject('Missing selected record');
            }
            if (this.state.selectedIoTDeviceID == null){
                this.parentWidget.do_warn('Please select device!');
                return Promise.reject('Missing selected device');
            }
            if (this.state.copies <= 0){
                this.parentWidget.do_warn('Please enter the number of copies!');
                return Promise.reject('Missing copies');
            }
            this.parentWidget.onPrint(this.state.selectedIoTDeviceID, this.state.copies, this.state.selectedRecordID);
        }

        onClose(ev){
            this.parentWidget.onClose();
        }

        mounted(){
            super.mounted(...arguments);
            if (this.default_device.el){
                this.default_device.el.click();
            }
        }

    }

    IoTPrintingActionContent.template = 'IoTPrintingActionContentContent';
    IoTPrintingActionContent.components = {IoTPrintingActionButtons};

    var IoTPrintingAction = AbstractAction.extend({
        contentTemplate: "printing_by_iot.IoTPrintingAction",

        init: function(parent, options){
            this._super.apply(this, arguments);
            this.resModel = options.context.default_res_model;
            this.resIDs = options.context.default_res_ids;
            this.copies = 1;
            this.actionID = options.context.default_action_report_id;
            this.printingServerActionID = options.context.printing_server_action_id;
            this.printFile = options.context.print_file;
            this.labels = options.context.labels;
            this.selectedRecords = options.context.selected_records;
            this.selectedTitle = options.context.selected_title;
            this.printers = [];
            this._getActionModel();
        },

        _getActionModel(){
            if (this.resModel == 'stock.move.line'){
                this.actionModel = 'print.move.line.record.label.create';
            }else{
                this.actionModel = 'print.individual.record.label.create';
            }
        },

        start() {
            this._super.apply(this, arguments);
            let self = this;
            this.container = this.el.getElementsByClassName("o_iot_printing_action")[0];
            this._rpc({
                model: 'iot.device',
                method: 'get_printers',
                args: [[], self.printingServerActionID]
            }).then(function(printers){
                self._updatePrinters(printers);
            });
        },

        _updatePrinters(printers){
            this.printers = printers;
            this.content = new IoTPrintingActionContent(this, {
                printers: printers, selectedRecords: this.selectedRecords, selectedTitle: this.selectedTitle});
            this.content.mount(this.container);
        },

        _updateDefaultPrinter(printerID){
            let self = this;
            this._rpc({
                model: 'iot.device',
                method: 'update_default_printer',
                args: [[], self.printingServerActionID, printerID]
            })
        },

        onClose(){
            this.do_action({type: 'ir.actions.act_window_close'});
        },

        _onValueChange: function (data) {
            if (data.status) {
                this.do_notify(false, _t("Printer ") + data.status);
            }
        },

        _onIoTActionResult: function (data){
            if (data.result === true) {
                this.do_notify(false, _t('Successfully sent to printer!'));
            } else {
                this.do_warn(_t('Connection to printer failed'), _t('Check if the printer is still connected'));
            }
        },

        _onIoTActionFail: function (ip){
            // Display the generic warning message when the connection to the IoT box failed.
            this.call('iot_longpolling', '_doWarnFail', ip);
        },

        _printLabels(iot_ip, identifier, document){
            let self = this;
            let iot_device = new DeviceProxy(self, {iot_ip: iot_ip, identifier: identifier});
            iot_device.add_listener(this._onValueChange.bind(this));
            _.each(_.range(this.copies), function(i){
                iot_device.action({'document': document})
                    .then(function(data) {
                        self._onIoTActionResult.call(self, data);
                    }).guardedCatch(self._onIoTActionFail.bind(self, iot_ip));
                })
            this.onClose();
            return $.when();
        },

        _sendPrintingRequest(recordID){
            let self = this;
            this._rpc({
                model: this.actionModel,
                method: 'send',
                args: [[recordID]]
            }).then(function(result){
                self._printLabels(result[0], result[1], result[2]);
            })
        },

        _prepareActionModelVals(IoTDeviceID, copies, selectedRecordID){
            let vals = {
                res_model: this.resModel,
                res_ids: this.resIDs,
                copies: copies,
                iot_device_id: parseInt(IoTDeviceID),
                action_report_id: parseInt(this.actionID)
            };
            if (this.resModel == 'stock.move.line'){
                vals.product_id = parseInt(selectedRecordID);
            }
            return vals
        },

        onPrint: function(IoTDeviceID, copies, selectedRecordID){
            let self = this;
            this.copies = copies;
            this._updateDefaultPrinter(IoTDeviceID);
            if (this.printFile){
                let printer = _.find(this.printers, function(printer){ return printer.id == parseInt(IoTDeviceID)});
                _.each(this.labels, function(label){
                    self._printLabels(printer.iot_ip, printer.identifier, label);
                })
            }else{
                return this._rpc({
                    model: this.actionModel,
                    method: 'create',
                    args: [
                        this._prepareActionModelVals(IoTDeviceID, copies, selectedRecordID)
                    ],
                }).then(function(recordID){
                    self._sendPrintingRequest(recordID)
                });
            }
        },
    });

    core.action_registry.add('action.iot_printing', IoTPrintingAction);

    return IoTPrintingAction;
});