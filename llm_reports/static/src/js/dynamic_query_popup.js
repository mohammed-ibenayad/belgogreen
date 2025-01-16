odoo.define('dynamic_query_report.DynamicQueryPopup', function (require) {
    "use strict";

    var core = require('web.core');
    var Dialog = require('web.Dialog');
    var rpc = require('web.rpc');

    var DynamicQueryPopup = {
        open: function () {
            var self = this;

            // Create the dialog
            var dialog = new Dialog(this, {
                title: 'Dynamic Query Report',
                size: 'medium',
                buttons: [
                    {
                        text: 'Submit',
                        click: function () {
                            var input = this.$('textarea').val();
                            if (input) {
                                // Call the Python method to process the input
                                rpc.query({
                                    model: 'dynamic.query.report',
                                    method: 'process_input',
                                    args: [input],
                                }).then(function (result) {
                                    // Display the result (e.g., a notification)
                                    self.do_action(result);
                                });
                            }
                            dialog.close();
                        },
                    },
                    {
                        text: 'Cancel',
                        close: true,
                    },
                ],
            });

            // Add a textarea for user input
            dialog.$el.append('<textarea class="form-control" rows="5"></textarea>');
            dialog.open();
        },
    };

    core.action_registry.add('dynamic_query_popup', DynamicQueryPopup);
    return DynamicQueryPopup;
});