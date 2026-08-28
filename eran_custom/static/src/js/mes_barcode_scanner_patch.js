/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { BarcodeDialog } from "@web/webclient/barcode/barcode_scanner";

// Scanner Odoo secara bawaan hanya mendeteksi barcode di dalam kotak crop.
// Pada kamera desktop kotak tersebut sering tidak sejalan dengan preview,
// sehingga barcode terlihat tetapi tidak pernah terbaca.
patch(BarcodeDialog.prototype, "eran_custom.BarcodeDialog", {
    async detectCode() {
        try {
            const codes = await this.detector.detect(this.videoPreviewRef.el);
            if (codes.length) {
                this.onResult(codes[0].rawValue);
            }
        } catch (error) {
            this.onError(error);
        }
    },
});
