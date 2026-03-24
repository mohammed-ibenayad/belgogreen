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
        if (!simulationId) {
            this.notification.add("Erreur: simulation introuvable.", { type: "danger" });
            this.action.doAction({ type: "ir.actions.act_window_close" });
            return;
        }
        try {
            await this.orm.call("pv.simulation", "action_do_regenerate", [[simulationId]]);
            this.notification.add("Simulation régénérée avec succès.", { type: "success" });
        } catch (e) {
            this.notification.add("Erreur lors de la régénération: " + (e.data?.message || e.message || "erreur inconnue"), { type: "danger" });
        }
        // Navigate back to the simulation form (restore previous breadcrumb)
        this.action.restore();
    }
}

registry.category("actions").add("pv_simulation_regenerate", PvSimulationRegenerate);

class PvSimulationGenerate extends Component {
    static template = "bgg_pv_simulation.GenerateLoading";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this._doGenerate();
    }

    async _doGenerate() {
        const simulationId = this.props.action.context.simulation_id;
        if (!simulationId) {
            this.notification.add("Erreur: simulation introuvable.", { type: "danger" });
            this.action.doAction({ type: "ir.actions.act_window_close" });
            return;
        }
        try {
            await this.orm.call("pv.simulation", "action_do_generate", [[simulationId]]);
            this.notification.add("Simulation générée avec succès.", { type: "success" });
        } catch (e) {
            this.notification.add("Erreur lors de la génération: " + (e.data?.message || e.message || "erreur inconnue"), { type: "danger" });
        }
        // Navigate to the simulation form
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "pv.simulation",
            res_id: simulationId,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

registry.category("actions").add("pv_simulation_generate", PvSimulationGenerate);
