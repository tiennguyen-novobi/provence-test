odoo.define('wave_picking_barcode.WavePickingBatchKanbanRecord', function (require) {
'use strict';

var KanbanRecord = require('web.KanbanRecord');

const StockBarcodeWavePickingBatch = KanbanRecord.include({
    /**
     * @override
     * @private
     */
    _openRecord: function () {
        if (this.modelName === 'stock.picking.batch' && this.$el.parents('.o_stock_barcode_kanban').length) {
            var self = this;
            this._rpc({
                model: 'stock.picking.batch',
                method: 'open_batch_picking_client_action',
                args: [self.id],
            })
            .then(function (action) {
                self.do_action(action);
            });
        } else {
            this._super.apply(this, arguments);
        }
    }
});

return StockBarcodeWavePickingBatch;
});