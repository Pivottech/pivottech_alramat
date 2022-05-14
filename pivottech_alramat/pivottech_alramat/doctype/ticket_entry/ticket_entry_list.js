frappe.listview_settings['ticket Entry'] = {
    onload: function(list_view){
        let me = this;
        list_view.page.add_inner_button(__("Bulk ticket entries"), function(){
            me.dialog = new frappe.ui.Dialog({
                fields: [
                    {
                        fieldtype: "Attach",
                        fieldname: "excel",
                        label: "Excel"
                    }
                ],
                primary_action_label: __("Submit"),
                primary_action: function(values){
                    frappe.call({
                        method: "pivottech_alramat.pivottech_alramat.doctype.ticket_entry.ticket_entry.insert_tickets",
                        args:{
                            filepath: values.excel
                        },
                        callback: function(res){
                            console.log(res.message);
                        }
                    })
                    me.dialog.hide();
                }
            });
            me.dialog.show();
        });
    }
}
