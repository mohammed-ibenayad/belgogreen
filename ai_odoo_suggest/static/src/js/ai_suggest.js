/** @odoo-module **/

import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

// Handle AI suggestion confirm/reject buttons in chat messages
document.addEventListener('DOMContentLoaded', function() {
    // Handle AI suggestion confirm buttons
    document.addEventListener('click', function(event) {
        const confirmBtn = event.target.closest('.ai-confirm');
        if (confirmBtn) {
            const suggestionId = parseInt(confirmBtn.dataset.suggestionId);
            const actionIndex = parseInt(confirmBtn.dataset.actionIndex);
            
            rpc('/web/dataset/call_kw/ai.odoo.suggest/confirm_action', {
                model: 'ai.odoo.suggest',
                method: 'confirm_action',
                args: [[suggestionId], actionIndex],
                kwargs: {}
            }).then(function(result) {
                if (result && result.success) {
                    console.log('Action confirmed');
                    // Optionally reload or update the UI
                    confirmBtn.disabled = true;
                    confirmBtn.textContent = '✓ Confirmed';
                }
            }).catch(function(error) {
                console.error('Error confirming action:', error);
            });
        }
        
        // Handle AI suggestion reject buttons
        const rejectBtn = event.target.closest('.ai-reject');
        if (rejectBtn) {
            const suggestionId = parseInt(rejectBtn.dataset.suggestionId);
            const actionIndex = parseInt(rejectBtn.dataset.actionIndex);
            
            rpc('/web/dataset/call_kw/ai.odoo.suggest/reject_action', {
                model: 'ai.odoo.suggest',
                method: 'reject_action',
                args: [[suggestionId], actionIndex],
                kwargs: {}
            }).then(function(result) {
                if (result && result.success) {
                    console.log('Action rejected');
                    // Optionally reload or update the UI
                    rejectBtn.disabled = true;
                    rejectBtn.textContent = '✗ Rejected';
                }
            }).catch(function(error) {
                console.error('Error rejecting action:', error);
            });
        }
    });
});