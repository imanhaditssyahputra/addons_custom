/** @odoo-module **/

import { registry } from "@web/core/registry";

const mesEditRequestService = {
    dependencies: ["bus_service", "notification", "orm"],

    start(env, { bus_service, notification, orm }) {

        console.log("==========================================");
        console.log("MES EDIT REQUEST BUS LISTENER STARTED");
        console.log("==========================================");
        console.log("MES: waiting for partner-targeted bus notification");

        loadPendingEditRequests(orm, notification);

        // =====================================================
        // LISTEN BUS NOTIFICATION
        // =====================================================

        bus_service.addEventListener(
            "notification",
            ({ detail: notifications }) => {

                console.log("MES BUS NOTIFICATION:", notifications);

                for (const notification_data of notifications) {

                    const { type, payload } = notification_data;

                    console.log("MES BUS EVENT:", type, payload);

                    if (type === "mes_edit_request") {
                        console.log("🔥 MES EDIT REQUEST RECEIVED:", payload);
                        enqueueEditRequestPopup(payload, orm, notification);
                    }
                }
            }
        );

        console.log("MES EDIT REQUEST LISTENER READY");

        // =====================================================
        // HANDLE TOMBOL EDIT (event delegation)
        // =====================================================

        document.addEventListener("click", async (e) => {
            const btn = e.target.closest("[data-mes-edit]");
            if (!btn) return;

            const lineId = btn.dataset.mesEdit;
            btn.disabled = true;
            btn.innerText = "⏳...";

            const backdrop = document.createElement("div");
            Object.assign(backdrop.style, {
                position: "fixed", inset: "0",
                background: "rgba(0,0,0,0.55)",
                zIndex: "99999", display: "flex",
                alignItems: "center", justifyContent: "center",
            });

            const box = document.createElement("div");
            Object.assign(box.style, {
                background: "white", borderRadius: "12px",
                padding: "28px 24px", width: "340px",
                maxWidth: "90vw", textAlign: "center",
                boxShadow: "0 8px 32px rgba(0,0,0,0.25)",
                fontFamily: "Arial,sans-serif",
            });

            box.innerHTML = `
                <div style="font-size:36px;margin-bottom:10px;">⚠️</div>
                <h3 style="margin:0 0 8px;">Ajukan Edit?</h3>
                <p style="color:#777;font-size:13px;margin-bottom:20px;">
                    Permintaan edit akan dikirim ke Leader untuk disetujui.
                </p>
                <div style="display:flex;gap:10px;">
                    <button id="mes-edit-cancel" style="flex:1;padding:12px;border:none;
                        border-radius:6px;background:#6c757d;color:white;
                        font-size:14px;cursor:pointer;">Batal</button>
                    <button id="mes-edit-confirm" style="flex:1;padding:12px;border:none;
                        border-radius:6px;background:#0b72b9;color:white;
                        font-size:14px;font-weight:bold;cursor:pointer;">Ya, Ajukan</button>
                </div>
            `;

            backdrop.appendChild(box);
            document.body.appendChild(backdrop);

            box.querySelector("#mes-edit-cancel").onclick = () => {
                backdrop.remove();
                btn.disabled = false;
                btn.innerText = "✏️ Edit";
            };

            box.querySelector("#mes-edit-confirm").onclick = async () => {
                box.querySelector("#mes-edit-confirm").disabled = true;
                box.querySelector("#mes-edit-confirm").innerText = "⏳...";

                try {
                    const resp = await fetch(`/mes/edit/${lineId}/request-json`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({}),
                    });
                    const data = await resp.json();
                    backdrop.remove();

                    const rb = document.createElement("div");
                    Object.assign(rb.style, {
                        position: "fixed", inset: "0",
                        background: "rgba(0,0,0,0.55)",
                        zIndex: "99999", display: "flex",
                        alignItems: "center", justifyContent: "center",
                    });

                    const rbox = document.createElement("div");
                    Object.assign(rbox.style, {
                        background: "white", borderRadius: "12px",
                        padding: "28px 24px", width: "340px",
                        maxWidth: "90vw", textAlign: "center",
                        boxShadow: "0 8px 32px rgba(0,0,0,0.25)",
                    });

                    const ok = data.success;
                    rbox.innerHTML = `
                        <div style="font-size:36px;margin-bottom:10px;">
                            ${ok ? "✅" : "❌"}
                        </div>
                        <h3 style="margin:0 0 8px;color:${ok ? "#28a745" : "#dc3545"};">
                            ${ok ? "Request Terkirim" : "Gagal"}
                        </h3>
                        <p style="color:#555;font-size:13px;margin-bottom:20px;">
                            ${data.message || "-"}
                        </p>
                        <button id="mes-edit-ok" style="width:100%;padding:12px;border:none;
                            border-radius:6px;background:${ok ? "#28a745" : "#dc3545"};
                            color:white;font-size:14px;font-weight:bold;cursor:pointer;">
                            OK
                        </button>
                    `;

                    rb.appendChild(rbox);
                    document.body.appendChild(rb);

                    rbox.querySelector("#mes-edit-ok").onclick = () => {
                        rb.remove();
                        window.location.reload();
                    };

                } catch (err) {
                    backdrop.remove();
                    btn.disabled = false;
                    btn.innerText = "✏️ Edit";
                    notification.add("Terjadi kesalahan. Silakan coba lagi.", { type: "danger" });
                }
            };
        });

    }, // ← tutup start()
};

// =============================================================
// REGISTER SERVICE
// =============================================================

registry
    .category("services")
    .add("mes_edit_request_service", mesEditRequestService);

// =============================================================
// POPUP
// =============================================================

const queuedEditRequestIds = new Set();
let editRequestPopupChain = Promise.resolve();

async function loadPendingEditRequests(orm, notification) {
    try {
        const pending = await orm.call(
            "mes.scan.approval.edit.request",
            "get_pending_for_current_leader",
            []
        );
        for (const payload of pending || []) {
            enqueueEditRequestPopup(payload, orm, notification);
        }
    } catch (error) {
        console.warn("MES: gagal memuat request edit yang menunggu", error);
    }
}

function enqueueEditRequestPopup(payload, orm, notification) {
    const requestId = payload && payload.request_id;
    if (!requestId || queuedEditRequestIds.has(requestId)) {
        return;
    }
    queuedEditRequestIds.add(requestId);
    editRequestPopupChain = editRequestPopupChain
        .then(() => new Promise((resolve) => {
            showEditRequestPopup(payload, orm, notification, resolve);
        }))
        .finally(() => {
            queuedEditRequestIds.delete(requestId);
        });
}

function showEditRequestPopup(payload, orm, notification, onDone) {

    // Jangan tampilkan popup dua kali
    const existing = document.getElementById(
        "mes-edit-request-popup"
    );

    if (existing && existing.dataset.requestId === String(payload.request_id)) {
        if (onDone) {
            onDone();
        }
        return;
    }

    if (existing) {
        existing.remove();
    }


    // =========================================================
    // BACKDROP
    // =========================================================

    const backdrop = document.createElement("div");

    backdrop.id =
        "mes-edit-request-popup";
    backdrop.dataset.requestId = payload.request_id;

    backdrop.style.position = "fixed";
    backdrop.style.top = "0";
    backdrop.style.left = "0";
    backdrop.style.right = "0";
    backdrop.style.bottom = "0";

    backdrop.style.background =
        "rgba(0,0,0,0.55)";

    backdrop.style.zIndex =
        "99999";

    backdrop.style.display =
        "flex";

    backdrop.style.alignItems =
        "center";

    backdrop.style.justifyContent =
        "center";


    // =========================================================
    // POPUP
    // =========================================================

    const popup = document.createElement("div");

    popup.style.width =
        "520px";

    popup.style.maxWidth =
        "90vw";

    popup.style.background =
        "white";

    popup.style.borderRadius =
        "12px";

    popup.style.boxShadow =
        "0 10px 40px rgba(0,0,0,0.35)";

    popup.style.overflow =
        "hidden";

    popup.style.fontFamily =
        "Arial, sans-serif";


    // =========================================================
    // HEADER
    // =========================================================

    const header = document.createElement("div");

    header.style.background =
        "#0b72b9";

    header.style.color =
        "white";

    header.style.padding =
        "18px 22px";

    header.innerHTML = `
        <div style="
            font-size:20px;
            font-weight:bold;
        ">
            🔔 Request Edit
        </div>

        <div style="
            font-size:13px;
            margin-top:4px;
            opacity:0.9;
        ">
            Membutuhkan persetujuan Leader
        </div>
    `;


    // =========================================================
    // BODY
    // =========================================================

    const body = document.createElement("div");

    body.style.padding =
        "22px";


    body.innerHTML = `

        <div style="
            margin-bottom:16px;
        ">

            <div style="
                color:#777;
                font-size:12px;
            ">
                Operator
            </div>

            <div style="
                font-size:16px;
                font-weight:bold;
            ">
                ${escapeHtml(
                    payload.operator_name || "-"
                )}
            </div>

        </div>


        <div style="
            margin-bottom:16px;
        ">

            <div style="
                color:#777;
                font-size:12px;
            ">
                Work Order
            </div>

            <div style="
                font-size:16px;
                font-weight:bold;
            ">
                ${escapeHtml(
                    payload.workorder_name || "-"
                )}
            </div>

        </div>


        <div style="
            margin-bottom:16px;
        ">

            <div style="
                color:#777;
                font-size:12px;
            ">
                Manufacturing Order
            </div>

            <div style="
                font-size:14px;
            ">
                ${escapeHtml(
                    payload.production_name || "-"
                )}
            </div>

        </div>


        <div style="
            margin-bottom:16px;
        ">

            <div style="
                color:#777;
                font-size:12px;
            ">
                Product
            </div>

            <div style="
                font-size:14px;
            ">
                ${escapeHtml(
                    payload.product_name || "-"
                )}
            </div>

        </div>


        <div style="
            background:#f8f9fa;
            border-radius:8px;
            padding:12px;
            margin-top:18px;
        ">

            <div style="
                color:#777;
                font-size:12px;
            ">
                Output Saat Ini
            </div>

            <div style="
                font-size:24px;
                font-weight:bold;
                color:#0b72b9;
            ">
                ${payload.current_qty ?? 0}
            </div>

        </div>

    `;


    // =========================================================
    // FOOTER
    // =========================================================

    const footer = document.createElement("div");

    footer.style.display =
        "flex";

    footer.style.justifyContent =
        "flex-end";

    footer.style.gap =
        "10px";

    footer.style.padding =
        "15px 22px";

    footer.style.borderTop =
        "1px solid #eee";


    // =========================================================
    // TOLAK
    // =========================================================

    const rejectButton =
        document.createElement("button");

    rejectButton.innerText =
        "❌ Tolak";

    rejectButton.style.padding =
        "9px 18px";

    rejectButton.style.border =
        "none";

    rejectButton.style.borderRadius =
        "6px";

    rejectButton.style.background =
        "#dc3545";

    rejectButton.style.color =
        "white";

    rejectButton.style.cursor =
        "pointer";


    // =========================================================
    // SETUJUI
    // =========================================================

    const approveButton =
        document.createElement("button");

    approveButton.innerText =
        "Setujui";

    approveButton.style.padding =
        "9px 18px";

    approveButton.style.border =
        "none";

    approveButton.style.borderRadius =
        "6px";

    approveButton.style.background =
        "#28a745";

    approveButton.style.color =
        "white";

    approveButton.style.cursor =
        "pointer";


    // =========================================================
    // BUTTON ACTION
    // =========================================================

    rejectButton.onclick = async () => {

        console.log(
            "Reject clicked:",
            payload.request_id
        );

        try {
            await orm.call("mes.scan.approval.edit.request", "action_reject", [[payload.request_id]]);
            backdrop.remove();
            if (onDone) {
                onDone("rejected");
            }
        } catch (error) {
            notification.add(error.message || "Request edit gagal ditolak.", { type: "danger" });
        }
    };


    approveButton.onclick = async () => {

        console.log(
            "Open approval:",
            payload.request_id
        );

        try {
            approveButton.disabled = true;
            backdrop.remove();
            showQtyEditPopup(payload, orm, notification, onDone);
        } catch (error) {
            approveButton.disabled = false;
            notification.add(error.message || "Request edit gagal disetujui.", { type: "danger" });
        }
    };


    footer.appendChild(
        rejectButton
    );

    footer.appendChild(
        approveButton
    );


    // =========================================================
    // ASSEMBLE
    // =========================================================

    popup.appendChild(
        header
    );

    popup.appendChild(
        body
    );

    popup.appendChild(
        footer
    );

    backdrop.appendChild(
        popup
    );

    document.body.appendChild(
        backdrop
    );
}


// =============================================================
// POPUP PENGINGAT MEMO IT
// =============================================================

function showQtyEditPopup(payload, orm, notification, onDone) {
    const backdrop = document.createElement("div");
    backdrop.id = "mes-qty-edit-popup";
    Object.assign(backdrop.style, {
        position: "fixed", inset: "0", background: "rgba(0,0,0,0.55)",
        zIndex: "99999", display: "flex", alignItems: "center", justifyContent: "center",
    });

    const popup = document.createElement("div");
    Object.assign(popup.style, {
        width: "440px", maxWidth: "90vw", background: "white", borderRadius: "12px",
        boxShadow: "0 10px 40px rgba(0,0,0,0.35)", overflow: "hidden", fontFamily: "Arial, sans-serif",
    });
    popup.innerHTML = `
        <div style="background:#0b72b9;color:white;padding:18px 22px;">
            <div style="font-size:20px;font-weight:bold;">Ubah Output</div>
            <div style="font-size:13px;margin-top:4px;opacity:0.9;">
                Masukkan output terbaru yang benar
            </div>
        </div>
        <div style="padding:22px;">
            <div style="color:#777;font-size:12px;">Output Saat Ini</div>
            <div style="font-size:22px;font-weight:bold;color:#0b72b9;margin-bottom:16px;">
                ${payload.current_qty ?? 0}
            </div>
            <label style="display:block;color:#777;font-size:12px;margin-bottom:6px;">
                Output Baru
            </label>
            <input id="mes-new-qty-input" type="number" min="0.01" step="0.01"
                value="${payload.current_qty ?? 0}"
                style="width:100%;box-sizing:border-box;padding:10px 12px;border:1px solid #ccc;
                border-radius:6px;font-size:18px;font-weight:bold;"/>
            <div id="mes-qty-over-target" style="display:none;color:#dc3545;font-size:13px;font-weight:bold;margin-top:8px;">
                Output Melebihi Target
            </div>
        </div>
    `;

    const footer = document.createElement("div");
    Object.assign(footer.style, {
        padding: "15px 22px", borderTop: "1px solid #eee",
        display: "flex", justifyContent: "flex-end", gap: "10px",
    });

    const cancelButton = document.createElement("button");
    cancelButton.innerText = "Batal";
    Object.assign(cancelButton.style, {
        padding: "9px 18px", border: "none", borderRadius: "6px",
        background: "#6c757d", color: "white", cursor: "pointer",
    });
    cancelButton.onclick = () => {
        backdrop.remove();
        showEditRequestPopup(payload, orm, notification, onDone);
    };

    const okButton = document.createElement("button");
    okButton.innerText = "OK";
    Object.assign(okButton.style, {
        padding: "9px 22px", border: "none", borderRadius: "6px",
        background: "#28a745", color: "white", cursor: "pointer",
    });
    okButton.onclick = async () => {
        const input = popup.querySelector("#mes-new-qty-input");
        const newQty = parseFloat(input && input.value);
        if (!newQty || newQty <= 0) {
            notification.add("Masukkan output terbaru yang benar.", { type: "danger" });
            return;
        }
        const targetQty = parseFloat(payload.qty_target) || 0;
        if (targetQty > 0 && newQty > targetQty) {
            return;
        }
        try {
            okButton.disabled = true;
            await orm.call(
                "mes.scan.approval.edit.request",
                "action_approve",
                [[payload.request_id]],
                { new_qty: newQty }
            );
            backdrop.remove();
            if (onDone) {
                onDone("approved");
            }
            showMemoReminderPopup({ ...payload, new_qty: newQty }, orm, notification);
        } catch (error) {
            okButton.disabled = false;
            notification.add(error.message || "Request edit gagal disetujui.", { type: "danger" });
        }
    };

    footer.appendChild(cancelButton);
    footer.appendChild(okButton);
    popup.appendChild(footer);
    backdrop.appendChild(popup);
    document.body.appendChild(backdrop);
    const qtyInput = popup.querySelector("#mes-new-qty-input");
    const overMsg = popup.querySelector("#mes-qty-over-target");
    const targetQty = parseFloat(payload.qty_target) || 0;
    const refreshOverTarget = () => {
        const newQty = parseFloat(qtyInput && qtyInput.value) || 0;
        const over = targetQty > 0 && newQty > targetQty;
        if (overMsg) overMsg.style.display = over ? "block" : "none";
        okButton.disabled = over;
        okButton.style.opacity = over ? "0.45" : "1";
        okButton.style.cursor = over ? "not-allowed" : "pointer";
    };
    if (qtyInput) {
        qtyInput.addEventListener("input", refreshOverTarget);
        qtyInput.focus();
        qtyInput.select();
        refreshOverTarget();
    }
}

function showMemoReminderPopup(payload, orm, notification) {
    const backdrop = document.createElement("div");
    backdrop.id = "mes-memo-reminder-popup";
    Object.assign(backdrop.style, {
        position: "fixed", inset: "0", background: "rgba(0,0,0,0.55)",
        zIndex: "99999", display: "flex", alignItems: "center", justifyContent: "center",
    });

    const popup = document.createElement("div");
    Object.assign(popup.style, {
        width: "440px", maxWidth: "90vw", background: "white", borderRadius: "12px",
        boxShadow: "0 10px 40px rgba(0,0,0,0.35)", overflow: "hidden", fontFamily: "Arial, sans-serif",
    });
    popup.innerHTML = `
        <div style="background:#0b72b9;color:white;padding:18px 22px;font-size:20px;font-weight:bold">
            Request Edit Disetujui
        </div>
        <div style="padding:28px 22px;font-size:16px;line-height:1.5">
            Output sudah diubah menjadi <b>${payload.new_qty ?? "-"}</b>.<br/><br/>
            Segera Buat Memo ke Tim IT Untuk Perubahan Data.
        </div>`;

    const footer = document.createElement("div");
    Object.assign(footer.style, {
        padding: "15px 22px", borderTop: "1px solid #eee", textAlign: "right",
    });
    const okButton = document.createElement("button");
    okButton.innerText = "OK";
    Object.assign(okButton.style, {
        padding: "9px 22px", border: "none", borderRadius: "6px", background: "#28a745",
        color: "white", cursor: "pointer",
    });
    okButton.onclick = async () => {
        try {
            okButton.disabled = true;
            await orm.call("mes.scan.approval.edit.request", "action_confirm_it_memo", [[payload.request_id]]);
            backdrop.remove();
        } catch (error) {
            okButton.disabled = false;
            notification.add(error.message || "Notifikasi admin gagal dikirim.", { type: "danger" });
        }
    };

    footer.appendChild(okButton);
    popup.appendChild(footer);
    backdrop.appendChild(popup);
    document.body.appendChild(backdrop);
}

// =============================================================
// ESCAPE HTML
// =============================================================

function escapeHtml(value) {
    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
