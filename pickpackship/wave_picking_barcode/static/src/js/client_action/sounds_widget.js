odoo.define('wave_picking_barcode.SoundsWidget', function (require) {
    'use strict';

    var Widget = require('web.Widget');

    var SoundsWidget = Widget.extend({
        template: 'sounds_widget',

        start: function(){
            this._super.apply(this, arguments);
            this.$errorSound = this.$el.find('audio.error_sound').get(0);
            this.$notifySound = this.$el.find('audio.notify_sound').get(0);
        },

        playSound: function(type){
            try {
                let playPromise;
                switch (type){
                    case 'error':
                        playPromise = this.$errorSound.play();
                        break;
                    case 'notify':
                        playPromise = this.$notifySound.play();
                        break;
                    default:
                        break;
                }

                if (playPromise !== undefined){
                    playPromise.then(_ => {}).catch(err => { console.log(err.message); });
                }
            } catch(err) {
                console.error(err.message);
            }
        }
    })

    return SoundsWidget
})