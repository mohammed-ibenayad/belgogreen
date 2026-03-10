/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component } from "@odoo/owl";

class PvSimulationRegenerate extends Component {
    static template = "bgg_pv_simulation.RegenerateLoading";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this._doRegenerate();
    }

    async _doRegenerate() {
        const simulationId = this.props.action.context.simulation_id;
        try {
            await this.orm.call("pv.simulation", "action_do_regenerate", [[simulationId]]);
            this.notification.add("Simulation régénérée avec succès.", { type: "success" });
        } catch (e) {
            this.notification.add("Erreur lors de la régénération.", { type: "danger" });
        }
        this.action.doAction({ type: "ir.actions.client", tag: "reload" });
    }
}

registry.category("actions").add("pv_simulation_regenerate", PvSimulationRegenerate);
