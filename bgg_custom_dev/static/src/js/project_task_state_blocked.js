/** @odoo-module **/

// "Bloqué" task state (bgg_custom_dev/models/project_task.py): red "ban" icon
// in Odoo's task state widget, offered on tasks of admin projects only (the
// views load x_is_admin_dossier_project). Rights are checked server side.
import { patch } from "@web/core/utils/patch";
import { ProjectTaskStateSelection } from "@project/components/project_task_state_selection/project_task_state_selection";

const BLOCKED = "05_blocked";

patch(ProjectTaskStateSelection.prototype, {
    setup() {
        super.setup(...arguments);
        this.icons[BLOCKED] = "fa fa-lg fa-ban";
        this.colorIcons[BLOCKED] = "text-danger";
        this.colorButton[BLOCKED] = "btn-outline-danger";
    },

    get options() {
        const options = super.options;
        const data = this.props.record.data;
        const current = data[this.props.name];
        if (current === BLOCKED || (data.x_is_admin_dossier_project && current !== "04_waiting_normal")) {
            const selection = this.props.record.fields[this.props.name].selection || [];
            const blocked = selection.find(([value]) => value === BLOCKED);
            if (blocked) {
                // before "Annulé" / "Terminé", like the other open states
                const index = options.findIndex(([value]) => value === "1_canceled");
                options.splice(index < 0 ? options.length : index, 0, blocked);
            }
        }
        return options;
    },
});
