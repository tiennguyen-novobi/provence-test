odoo.define('wave_picking_barcode.abstract_action_extend', function(require){
    'use strict'
    let AbstractAction = require('web.AbstractAction')

    let AbstractActionExtend = AbstractAction.extend({
        do_notify: function (title, message, sticky, className) {
            this.soundsWidget?.playSound('notify');
            this.displayNotification({
                "title": title,
                "message": message,
                "sticky": sticky,
                "className": className,
                "type": "info"
            })
        },

        do_warn: function (title, message, sticky, className) {
            this.soundsWidget?.playSound('error');
            this.displayNotification({
                "title": title,
                "message": message,
                "sticky": sticky,
                "className": className,
                "type": "danger"
            })
        }
    })

    return AbstractActionExtend
})