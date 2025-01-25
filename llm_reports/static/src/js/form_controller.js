/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";

patch(FormController.prototype, {
    setup() {
        super.setup();
        window.addEventListener('keydown', this._handleKeyDown.bind(this));
    },
    _handleKeyDown(event) {
        if (event.key === 'Enter' && !event.shiftKey && !event.ctrlKey) {
            const targetElement = event.target;
            if (targetElement.name === 'user_input') {
                event.preventDefault();  // Prevent newline
                const submitButton = document.querySelector('.btn-primary');
                if (submitButton) {
                    submitButton.click();
                }
            }
        }
    }
});