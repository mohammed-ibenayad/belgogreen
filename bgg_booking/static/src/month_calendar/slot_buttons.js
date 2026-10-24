import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/**
 * The free times of the chosen day as buttons (with the commercial when all
 * their times are listed). A click keeps the time on the form and goes on to
 * the client's details, through the form's own button flow (which saves the
 * form first: the times listed after a day click are not saved yet).
 */
export class BookingSlotButtons extends Component {
    static template = "bgg_booking.SlotButtons";
    static props = { ...standardFieldProps };

    get slots() {
        return this.props.record.data[this.props.name].records;
    }

    async choose(slot) {
        const record = this.props.record;
        await record.update({
            start: slot.data.start,
            slot_combination_id: slot.data.combination_id,
        });
        await this.env.onClickViewButton({
            clickParams: { type: "object", name: "action_details" },
            getResParams: () => ({
                context: record.context,
                evalContext: record.evalContext,
                resModel: record.resModel,
                resId: record.resId,
                resIds: [record.resId],
            }),
        });
    }
}

registry.category("fields").add("bgg_booking_slot_buttons", {
    component: BookingSlotButtons,
    supportedTypes: ["one2many"],
    relatedFields: [
        { name: "start", type: "datetime" },
        { name: "combination_id", type: "many2one", relation: "resource.booking.combination" },
        { name: "time_label", type: "char" },
        { name: "commercial_label", type: "char" },
    ],
});
