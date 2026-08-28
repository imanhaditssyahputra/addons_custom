/** @odoo-module **/

import { registry } from "@web/core/registry";

const mesEditRequestNotificationService = {
    dependencies: [
        "bus_service",
        "notification",
        "action",
    ],

    start(env, {
        bus_service,
        notification,
        action,
    }) {

        console.log(
            "MES EDIT REQUEST NOTIFICATION SERVICE STARTED"
        );

        // =====================================================
        // LISTEN REALTIME ODOO BUS
        // =====================================================

        bus_service.addEventListener(
            "notification",
            ({ detail: notifications }) => {

                for (const notificationItem of notifications) {

                    const {
                        type,
                        payload,
                    } = notificationItem;

                    // =================================================
                    // REQUEST EDIT BARU
                    // =================================================

                    // Request utama ditangani oleh popup custom di mes_edit_request.js.
                    if (false && type === "mes_edit_request") {

                        console.log(
                            "MES EDIT REQUEST RECEIVED:",
                            payload
                        );

                        const operatorName =
                            payload.operator_name || "-";

                        const workorderName =
                            payload.workorder_name || "-";

                        const productionName =
                            payload.production_name || "-";

                        const productName =
                            payload.product_name || "-";

                        const currentQty =
                            payload.current_qty ?? 0;

                        const requestId =
                            payload.request_id;

                        // =============================================
                        // TAMPILKAN POPUP / NOTIFICATION
                        // =============================================

                        notification.add(
                            `
                            Operator : ${operatorName}
                            Work Order : ${workorderName}
                            MO : ${productionName}
                            Product : ${productName}
                            Output Saat Ini : ${currentQty}
                            `,
                            {
                                title: "⚠️ REQUEST EDIT BARU",

                                type: "warning",

                                sticky: true,

                                buttons: [
                                    {
                                        name: "Buka Request",

                                        primary: true,

                                        onClick: () => {

                                            console.log(
                                                "Opening edit request:",
                                                requestId
                                            );

                                            // =================================
                                            // BUKA FORM REQUEST
                                            // =================================

                                            action.doAction({
                                                type: "ir.actions.act_window",

                                                res_model:
                                                    "mes.scan.approval.edit.request",

                                                res_id:
                                                    requestId,

                                                views: [
                                                    [
                                                        false,
                                                        "form"
                                                    ]
                                                ],

                                                target: "current",
                                            });
                                        },
                                    },
                                ],
                            }
                        );
                    }

                    // =================================================
                    // HASIL APPROVAL / REJECT
                    // =================================================

                    if (
                        type ===
                        "mes_edit_request_result"
                    ) {

                        console.log(
                            "MES EDIT REQUEST RESULT:",
                            payload
                        );

                        notification.add(
                            payload.message ||
                            "Status request edit berubah.",

                            {
                                title:
                                    payload.title ||
                                    "MES Edit Request",

                                type:
                                    payload.state ===
                                    "approved"
                                        ? "success"
                                        : "danger",

                                sticky: false,
                            }
                        );
                    }

                    // =================================================
                    // PENGAJUAN MEMO KE IT (KHUSUS ADMIN)
                    // =================================================

                    if (type === "mes_edit_request_admin_memo") {
                        let closeNotification;
                        closeNotification = notification.add(
                            payload.message ||
                            "Ada pengajuan memo dari Produksi terkait perubahan data.",
                            {
                                title: payload.title || "Pengajuan Memo Perubahan Data",
                                type: "warning",
                                sticky: true,
                                buttons: [
                                    {
                                        name: "OK",
                                        primary: true,
                                        onClick: () => closeNotification(),
                                    },
                                ],
                            }
                        );
                    }
                }
            }
        );

        console.log(
            "MES EDIT REQUEST BUS LISTENER READY"
        );
    },
};

registry
    .category("services")
    .add(
        "mes_edit_request_notification",
        mesEditRequestNotificationService
    );
