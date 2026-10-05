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
                        // Popup handled by mes_edit_request.js
                        continue;
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

                    if (type === "mes_edit_request_admin_memo") {
                        let closeNotification;
                        closeNotification = notification.add(
                            payload.message ||
                            `MO ${payload.production_name || "-"}, atas nama ${payload.operator_name || "-"}, tanggal ${payload.date_str || "-"}, Leader ${payload.leader_name || "-"} akan membuat memo terkait perubahan data output.`,
                            {
                                title: payload.title || "Pengajuan Memo Perubahan Data",
                                type: "warning",
                                sticky: true,
                                buttons: [
                                    {
                                        name: "OK",
                                        primary: true,
                                        onClick: () => {
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
