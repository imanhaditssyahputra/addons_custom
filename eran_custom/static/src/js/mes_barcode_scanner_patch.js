/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { BarcodeDialog } from "@web/webclient/barcode/barcode_scanner";
import { loadJS } from "@web/core/assets";
import { buildZXingBarcodeDetector } from "@web/webclient/barcode/ZXingBarcodeDetector";
import { onWillStart } from "@odoo/owl";

function decodeCanvasWithZXing(canvas) {
    const ZXing = window.ZXing;
    if (!ZXing || !canvas) {
        return [];
    }
    const formats = [
        ZXing.BarcodeFormat.CODE_128,
        ZXing.BarcodeFormat.CODE_39,
        ZXing.BarcodeFormat.QR_CODE,
        ZXing.BarcodeFormat.EAN_13,
        ZXing.BarcodeFormat.ITF,
    ];
    const hints = new Map([
        [ZXing.DecodeHintType.POSSIBLE_FORMATS, formats],
        [ZXing.DecodeHintType.TRY_HARDER, true],
    ]);
    if (ZXing.DecodeHintType.ALSO_INVERTED !== undefined) {
        hints.set(ZXing.DecodeHintType.ALSO_INVERTED, true);
    }
    const reader = new ZXing.MultiFormatReader();
    reader.setHints(hints);
    const luminanceSource = new ZXing.HTMLCanvasElementLuminanceSource(canvas);
    const binaryBitmap = new ZXing.BinaryBitmap(new ZXing.HybridBinarizer(luminanceSource));
    try {
        const result = reader.decode(binaryBitmap);
        return [{ rawValue: result.getText() }];
    } catch (err) {
        return [];
    }
}

function videoToCanvas(video, rotate90) {
    const canvas = document.createElement("canvas");
    const width = video.videoWidth;
    const height = video.videoHeight;
    if (!width || !height) {
        return canvas;
    }
    const ctx = canvas.getContext("2d");
    if (rotate90) {
        canvas.width = height;
        canvas.height = width;
        ctx.translate(height, 0);
        ctx.rotate(Math.PI / 2);
        ctx.drawImage(video, 0, 0);
    } else {
        canvas.width = width;
        canvas.height = height;
        ctx.drawImage(video, 0, 0);
    }
    return canvas;
}

patch(BarcodeDialog.prototype, "eran_custom.BarcodeDialog", {
    setup() {
        this._super(...arguments);
        onWillStart(async () => {
            await loadJS("/web/static/lib/zxing-library/zxing-library.js");
            const DetectorClass = buildZXingBarcodeDetector(window.ZXing);
            this.detector = new DetectorClass({
                formats: ["code_128", "code_39", "qr_code", "ean_13", "itf"],
            });
        });
    },

    async detectCode() {
        const video = this.videoPreviewRef.el;
        if (!video || !video.videoWidth) {
            return;
        }
        try {
            let codes = [];
            if (this.detector) {
                codes = await this.detector.detect(video);
            }
            if (!codes.length) {
                codes = decodeCanvasWithZXing(videoToCanvas(video, false));
            }
            if (!codes.length) {
                codes = decodeCanvasWithZXing(videoToCanvas(video, true));
            }
            if (codes.length && codes[0].rawValue) {
                this.onResult(codes[0].rawValue);
            }
        } catch (error) {
            // Jangan tutup scanner hanya karena satu frame gagal dibaca.
        }
    },
});
