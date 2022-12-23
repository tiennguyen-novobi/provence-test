/** @odoo-module **/
import MainComponent from '@stock_barcode/components/main';
import { patch } from 'web.utils';

patch(MainComponent.prototype, 'pb_multichannel_amazon', {

     printSlip() {
        var id = $("div#picking_id").text();
        var name = $("span.o_title").text();
        var ajax = new XMLHttpRequest();
        ajax.open("GET", "/report/shipping/labels/shipping_label_and_packing_slip?picking_id=" + id, true);
        ajax.responseType = "blob";
        ajax.onload = function (data) {
            console.log(data);
            console.log(this.response);
            const downloadUrl = URL.createObjectURL(this.response);
            const a = document.createElement("a");
            a.href = downloadUrl;
            a.download = "odoo_" + name + ".pdf";
            document.body.appendChild(a);
            a.click();
        }
        ajax.send(null);
    }
});

export default PBMainComponent;