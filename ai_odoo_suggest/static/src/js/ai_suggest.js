odoo.define('ai_odoo_suggest.AISuggest', function (require) {
    'use strict';

    var core = require('web.core');
    var rpc = require('web.rpc');

    $(document).ready(function() {
        // Handle AI suggestion confirm/reject buttons
        $(document).on('click', '.ai-confirm', function() {
            var suggestionId = $(this).data('suggestion-id');
            var actionIndex = $(this).data('action-index');
            
            rpc.query({
                model: 'ai.odoo.suggest',
                method: 'confirm_action',
                args: [suggestionId, actionIndex],
            }).then(function(result) {
                if (result.status === 'success') {
                    console.log('Action confirmed');
                }
            });
        });

        $(document).on('click', '.ai-reject', function() {
            var suggestionId = $(this).data('suggestion-id');
            var actionIndex = $(this).data('action-index');
            
            rpc.query({
                model: 'ai.odoo.suggest',
                method: 'reject_action',
                args: [suggestionId, actionIndex],
            }).then(function(result) {
                if (result.status === 'success') {
                    console.log('Action rejected');
                }
            });
        });
    });
});