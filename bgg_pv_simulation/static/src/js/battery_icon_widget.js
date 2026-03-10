/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/**
 * Battery icon widget — renders an SVG battery with fill level 0-7.
 *
 * Level 0: empty outline
 * Level 1-7: progressively filled from bottom to top (green)
 */
class BatteryIconWidget extends Component {
    static template = "bgg_pv_simulation.BatteryIcon";
    static props = { ...standardFieldProps };

    get level() {
        return this.props.record.data[this.props.name] || 0;
    }

    get fillColor() {
        return this.level === 0 ? "none" : "#27ae60";
    }

    /**
     * Returns the fill height (0-28px out of the 28px body area).
     * Level 0 = 0px, Level 7 = 28px.
     */
    get fillHeight() {
        return Math.round((this.level / 7) * 28);
    }

    /**
     * Y position for the fill rect (top of body is y=4, bottom is y=32).
     * Fill grows upward from bottom.
     */
    get fillY() {
        return 32 - this.fillHeight;
    }

    get title() {
        const lvl = this.level;
        if (lvl === 0) return "Pas de batterie";
        const pct = Math.round((lvl / 7) * 100);
        return `Charge: ${pct}%`;
    }
}

registry.category("fields").add("battery_icon", {
    component: BatteryIconWidget,
});
