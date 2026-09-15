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

                    if (type === "mes_edit_request") {

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
                    // LEADER APPROVAL BERHASIL
                    // =================================================

                    if (
                        type ===
                        "mes_edit_request_approved"
                    ) {

                        console.log(
                            "MES LEADER APPROVAL RECEIVED:",
                            payload
                        );

                        let closeNotification;

                        closeNotification = notification.add(
                            `
                            Segera buat Memo ke Tim IT
                            untuk perubahan data.

                            MO : ${payload.production_name || "-"}
                            Work Order : ${payload.workorder_name || "-"}
                            Operator : ${payload.operator_name || "-"}
                            `,
                            {
                                title:
                                    "⚠️ Approval Berhasil",

                                type:
                                    "warning",

                                sticky:
                                    true,

                                buttons: [
                                    {
                                        name:
                                            "OK",

                                        primary:
                                            true,

                                        onClick: () => {

                                            console.log(
                                                "Memo IT notification closed"
                                            );

                                            if (closeNotification) {
                                                closeNotification();
                                            }
                                        },
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

// =================================================
// MEMO IT BARU
// =================================================

if (
    type ===
    "mes_it_memo_request"
) {

    console.log(
        "MES IT MEMO REQUEST RECEIVED:",
        payload
    );

    let closeNotification;

    closeNotification = notification.add(
        `
        Produksi mengajukan Memo IT
        terkait perubahan data.

        MO : ${payload.production_name || "-"}
        Work Order : ${payload.workorder_name || "-"}
        Operator : ${payload.operator_name || "-"}
        Perubahan Qty :
        ${payload.current_qty ?? 0}
        → ${payload.new_qty ?? 0}
        `,
        {
            title:
                "⚠️ PENGAJUAN MEMO IT BARU",

            type:
                "warning",

            sticky:
                true,

            buttons: [
                {
                    name:
                        "OK",

                    primary:
                        true,

                    onClick: () => {

                        console.log(
                            "IT Memo notification closed"
                        );

                        if (closeNotification) {
                            closeNotification();
                        }
                    },
                },
            ],
        }
    );
}