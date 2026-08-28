/** @odoo-module **/

import { registry } from "@web/core/registry";

const mesEditRequestService = {
    dependencies: ["bus_service", "notification", "orm"],

    start(env, { bus_service, notification, orm }) {

        console.log(
            "=========================================="
        );

        console.log(
            "MES EDIT REQUEST BUS LISTENER STARTED"
        );

        console.log(
            "=========================================="
        );

        // =====================================================
        // SUBSCRIBE KE BUS
        // =====================================================

        console.log(
            "MES: waiting for partner-targeted bus notification"
        );

        // =====================================================
        // LISTEN NOTIFICATION
        // =====================================================

        bus_service.addEventListener(
            "notification",
            ({ detail: notifications }) => {

                console.log(
                    "MES BUS NOTIFICATION:",
                    notifications
                );

                for (const notification_data of notifications) {

                    const {
                        type,
                        payload,
                    } = notification_data;

                    console.log(
                        "MES BUS EVENT:",
                        type,
                        payload
                    );

                    // =================================================
                    // REQUEST EDIT
                    // =================================================

                    if (type === "mes_edit_request") {

                        console.log(
                            "🔥 MES EDIT REQUEST RECEIVED:",
                            payload
                        );

                        showEditRequestPopup(payload, orm, notification);
                    }
                }
            }
        );

        console.log(
            "MES EDIT REQUEST LISTENER READY"
        );
    },
};


// =============================================================
// REGISTER SERVICE
// =============================================================

registry
    .category("services")
    .add(
        "mes_edit_request_service",
        mesEditRequestService
    );


// =============================================================
// POPUP
// =============================================================

function showEditRequestPopup(payload, orm, notification) {

    // Jangan tampilkan popup dua kali
    const existing = document.getElementById(
        "mes-edit-request-popup"
    );

    if (existing) {
        existing.remove();
    }


    // =========================================================
    // BACKDROP
    // =========================================================

    const backdrop = document.createElement("div");

    backdrop.id =
        "mes-edit-request-popup";

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
            await orm.call("mes.scan.approval.edit.request", "action_approve", [[payload.request_id]]);
            backdrop.remove();
            showMemoReminderPopup(payload, orm, notification);
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
