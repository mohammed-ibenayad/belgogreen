/** @odoo-module **/

import { FormController } from "@web/views/form/form_controller";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";
import { useBus } from "@web/core/utils/hooks";

export class LLMHandlingController extends FormController {
    setup() {
        super.setup();
        this.notificationService = useService("notification");
        useBus(this.env.bus, "display_notification", (ev) => {
            this.notificationService.add(ev.detail.message, {
                title: ev.detail.title,
                type: ev.detail.type,
                sticky: ev.detail.sticky,
            });
        });
    }

    async _onButtonClicked(event) {
        if (event.detail.attrs.name !== 'process_input') {
            return super._onButtonClicked(event);
        }

        event.preventDefault();

        const $footer = this.el.querySelector('footer');
        const $spinner = $footer.querySelector('.oe_processing');
        const $buttons = $footer.querySelectorAll('button');
        const userInput = this.el.querySelector('[name="user_input"]').value;
        const recordId = this.el.dataset.id;

        try {
            $spinner.style.display = 'block';
            $buttons.forEach(button => button.disabled = true);

            const result = await rpc("/web/dataset/call_kw/dynamic.query.report/process_input_async", {
                model: "dynamic.query.report",
                method: "process_input_async",
                args: [userInput, recordId],
                kwargs: {},
            });

            if (result.success) {
                await this.do_action(result.action);
            } else {
                this.env.bus.trigger("display_notification", {
                    title: "Error",
                    message: result.error || "Processing failed",
                    type: 'danger',
                    sticky: true,
                });
            }
        } catch (error) {
            this.env.bus.trigger("display_notification", {
                title: "Error",
                message: error.message || "An unexpected error occurred",
                type: 'danger',
                sticky: true,
            });
        } finally {
            $spinner.style.display = 'none';
            $buttons.forEach(button => button.disabled = false);
        }
    }
}

LLMHandlingController.template = "llm_reports.LLMHandlingController";