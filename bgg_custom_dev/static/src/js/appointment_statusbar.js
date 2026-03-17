/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { StatusBarField } from "@web/views/fields/statusbar/statusbar_field";
import { useService } from "@web/core/utils/hooks";

const WIZARD_STATUSES = {
    attended: "bgg_custom_dev.action_appointment_status_attended",
    no_show: "bgg_custom_dev.action_appointment_status_no_show",
};

patch(StatusBarField.prototype, {
    setup() {
        super.setup(...arguments);
        this.actionService = useService("action");
    },

    async selectItem(item) {
        const { name, record } = this.props;
        const statusValue = item.value;
        const model = record.resModel || record.model;

        // Intercept appointment_status changes on calendar.event
        if (
            name === "appointment_status" &&
            model === "calendar.event" &&
            statusValue in WIZARD_STATUSES
        ) {
            await this.actionService.doAction(WIZARD_STATUSES[statusValue], {
                additionalContext: {
                    active_id: record.resId,
                    active_model: "calendar.event",
                },
            });
            return;
        }

        // Default behavior for all other statusbar fields
        await super.selectItem(...arguments);
    },
});
