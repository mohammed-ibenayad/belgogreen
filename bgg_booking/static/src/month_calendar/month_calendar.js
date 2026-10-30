import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

const { DateTime, Info } = luxon;

/**
 * Month calendar of "Prise de RDV": the days with free times, as the
 * Appointments booking page showed them. Clicking a day sets the date field
 * (the form then lists its free times); the arrows change the month field,
 * whose free times per day come in the `day_availability` field.
 */
export class BookingMonthCalendar extends Component {
    static template = "bgg_booking.MonthCalendar";
    static props = { ...standardFieldProps };

    get today() {
        return DateTime.local().startOf("day");
    }

    get month() {
        const data = this.props.record.data;
        return (data.month || data[this.props.name] || this.today).startOf("month");
    }

    get freeDays() {
        const availability = this.props.record.data.day_availability || {};
        return availability.days || {};
    }

    get monthLabel() {
        return this.month.toFormat("LLLL yyyy");
    }

    get weekdays() {
        return Info.weekdays("short");
    }

    get canGoBack() {
        return this.month > this.today.startOf("month");
    }

    get cells() {
        const selected = this.props.record.data[this.props.name];
        const selectedIso = selected ? selected.toISODate() : false;
        const first = this.month;
        const start = first.minus({ days: first.weekday - 1 });
        const weeks = Math.ceil((first.weekday - 1 + first.daysInMonth) / 7);
        const cells = [];
        for (let index = 0; index < weeks * 7; index++) {
            const day = start.plus({ days: index });
            const iso = day.toISODate();
            const inMonth = day.month === first.month;
            const free = inMonth ? this.freeDays[iso] || 0 : 0;
            let className = "btn o_bgg_day";
            if (!inMonth) {
                className += " invisible";
            } else if (iso === selectedIso && free) {
                className += " btn-primary fw-bold";
            } else if (free) {
                className += " btn-outline-primary fw-bold";
            } else {
                className += " btn-light text-muted";
            }
            cells.push({
                iso,
                day: day.day,
                className,
                disabled: !inMonth || !free,
                title: free ? _t("%s heure(s) libre(s)", free) : _t("Complet ou fermé"),
            });
        }
        return cells;
    }

    async selectDay(cell) {
        if (cell.disabled || this.props.readonly) {
            return;
        }
        await this.props.record.update({ [this.props.name]: DateTime.fromISO(cell.iso) });
    }

    async changeMonth(delta) {
        if (delta < 0 && !this.canGoBack) {
            return;
        }
        await this.props.record.update({ month: this.month.plus({ months: delta }) });
    }
}

registry.category("fields").add("bgg_booking_month_calendar", {
    component: BookingMonthCalendar,
    supportedTypes: ["date"],
    fieldDependencies: [
        { name: "month", type: "date" },
        { name: "day_availability", type: "json" },
    ],
});
