cur_frm.add_fetch('sales_order',  'project',  'project');
cur_frm.add_fetch('purchase_order',  'project',  'project');
cur_frm.add_fetch('sales_order',  'advanced_payment_insurance_rate',  'advanced_payment_insurance_rate');
cur_frm.add_fetch('purchase_order',  'advanced_payment_insurance_rate',  'advanced_payment_insurance_rate');
cur_frm.add_fetch('sales_order',  'initial_delivery_payment_insurance_rate',  'initial_delivery_payment_insurance_rate');
cur_frm.add_fetch('purchase_order',  'initial_delivery_payment_insurance_rate',  'initial_delivery_payment_insurance_rate');
cur_frm.add_fetch('sales_order',  'taxes_and_charges',  'sales_taxes_and_charges_template');
cur_frm.add_fetch('purchase_order',  'taxes_and_charges',  'purchase_taxes_and_charges_template');
cur_frm.add_fetch('sales_order',  'clearance_type',  'clearance_type');
cur_frm.add_fetch('purchase_order',  'clearance_type',  'clearance_type');


frappe.ui.form.on("Clearances", {
	refresha: function(frm){
		console.log("refresh")
		frm.add_custom_button(__('Return'),function(){ 
		frappe.model.open_mapped_doc({
			method:"advanced_elements.advanced_elements.doctype.clearances.clearances.make_return",
			frm:frm

		})
		},__('Create'));
		
	}
	,
	setup: function(frm) {
		frm.set_query("purchase_order", function() {
			return {
				filters: [
					["Purchase Order","docstatus", "=", "1"]
				]
			};
		});
	}
});

frappe.ui.form.on("Clearances", {
	refresh: function(frm){
		console.log("1")
		frm.add_custom_button(__('Return'),function(){
			console.log("press")
			frappe.model.open_mapped_doc({
				method:"construction.construction.doctype.clearances.clearances.make_return",
				frm:frm
			})
			},__('Create'));
        if ( frm.doc.docstatus==1  &&  (frm.doc.zatca_status=="Pending" || frm.doc.zatca_status=="Recustom_zatca_warningsjected"  || frm.doc.custom_zatca_warnings.includes("SANDBOX") ) ){
            console.log("!!!!!!!!!!!!!!11");
            frm.add_custom_button(__("Generate xml"), function() {
                frappe.call({
                    method:"first_xml",
                    doc:frm.doc,
                    args:{"show_alert":true},
                    callback(r){
                        if(r.message){
                            frm.reload_doc()
                            //console.log(r.message)
                            //let file_url = r.message.replace(/#/g, "%23");
                            //window.open(file_url);

                        }
                    }
                })
            });
        }

        if (frm.doc.xml_path && frm.doc.xml_path!="" && frm.doc.xml_path!= null){
			frm.add_custom_button(__("Download xml"), function() {
				window.open(frm.doc.xml_path);

			})
		}


        if (frm.doc.xml_path && frm.doc.xml_path!="" && frm.doc.xml_path!= null  &&(frm.doc.zatca_status=="Pending" || frm.doc.zatca_status=="Rejected"  || frm.doc.custom_zatca_warnings.includes("SANDBOX")  ) ){
			frm.add_custom_button(__("Compliance Check"), function() {
				frappe.call({
					method:"compliance",
					doc:frm.doc,
					freeze:true,
					freeze_message:__("Verifying Invoice"),
					callback(r){
						if(r.message){
							
							//frm.reload_doc()
						}
					}
				})
				
			})
		}


        if (frm.doc.docstatus==1 &&   !frm.doc.simple && frm.doc.xml_path!= null && frm.doc.xml_path!="" && (frm.doc.zatca_status=="Pending" || frm.doc.zatca_status=="Rejected" || frm.doc.custom_zatca_warnings.includes("SANDBOX"))){
			frm.add_custom_button(__("Clears"), function() {
				frappe.call({
					method:"clearance",
					freeze:true,
					freeze_message:__("Clearing Invoice"),
					doc:frm.doc,
					callback(r){
						if(r.message){
							frm.reload_doc();
						}
					}
				})
			})

		}

	},
	setup: function(frm) {
		frm.set_query("sales_order", function() {
			return {
				filters: [
					["Sales Order","docstatus", "=", "1"]
				]
			};
		});
	}
});

frappe.ui.form.on('Clearances',  'clearance_type',  function(frm) {
    if (cur_frm.doc.clearance_type != "Outgoing" && cur_frm.doc.sales_order) {
        cur_frm.set_value('sales_order', '');
        cur_frm.set_value('customer', '');
        cur_frm.set_value('sales_order_date', '');
        cur_frm.set_value('delivery_date', '');
        cur_frm.set_value('project', '');
        cur_frm.set_value('sales_taxes_and_charges_template', '');
        cur_frm.set_value('advanced_payment_insurance_rate', 0);
        cur_frm.set_value('initial_delivery_payment_insurance_rate', 0);
    }
    if (cur_frm.doc.clearance_type != "Incoming" && cur_frm.doc.purchase_order) {
        cur_frm.set_value('purchase_order', '');
        cur_frm.set_value('supplier', '');
        cur_frm.set_value('purchase_order_date', '');
        cur_frm.set_value('required_by_date', '');
        cur_frm.set_value('project', '');
        cur_frm.set_value('purchase_taxes_and_charges_template', '');
        cur_frm.set_value('advanced_payment_insurance_rate', 0);
        cur_frm.set_value('initial_delivery_payment_insurance_rate', 0);
    }
	cur_frm.set_value('gross', 0);
	cur_frm.set_value('vat', 0);
	cur_frm.set_value('retention', 0);
	cur_frm.set_value('net_amount', 0);
	cur_frm.set_value('total_amount_before_vat', 0);
	cur_frm.set_value('advance_payment', 0);
	cur_frm.set_value('total_deduction_amount',0);
});

frappe.ui.form.on('Clearances',  'sales_order',  function(frm) {
    cur_frm.clear_table("items");
    cur_frm.clear_table("taxes");
	//cur_frm.clear_table('deductions_table');
console.log("wor");
console.log(cur_frm.doc.sales_order);
if (cur_frm.doc.sales_order){
frappe.call({
		doc : frm.doc,
		method: "get_sales_items",
		callback : function(r){
		refresh_field("items");

if(frm.doc.sales_taxes_and_charges_template){
                        frappe.call({
                                doc: frm.doc,
                                method: "get_sales_taxes",
                                    callback: function(r) {console.log(r);
                    refresh_field("taxes");
                    }
                        });
                }

		fix(frm);
}
});}

});
/*
frappe.ui.form.on('Clearances', {
    sales_order: function(frm) {
        if(cur_frm.doc.sales_order){
console.log("yoho");
           frappe.call({
                doc: frm.doc,
                  method: "get_sales_items",
                    callback: function(r) {
			console.log("items ");
			//frm.doc.items.forEach(function(item){ frappe.model.set_value('Clearance Items Table',item.name,'current_qty',item.qty-item.previous_qty);   });
                   refresh_field("items");
			//fix(frm);
                 }
           });
      }
	}
})

*/
frappe.ui.form.on('Clearances', {
    sales_taxes_and_charges_template: function(frm) {
console.log("taxes changed");
		if(frm.doc.sales_taxes_and_charges_template){
			frappe.call({
				doc: frm.doc,
				method: "get_sales_taxes",
				    callback: function(r) {
                    refresh_field("taxes");fix(frm);
                    }
			});
		} else { cur_frm.clear_table("taxes");refresh_field("taxes");}
	}
})

frappe.ui.form.on('Clearances',  'purchase_order',  function(frm) {
    cur_frm.clear_table("items");
    cur_frm.clear_table("taxes");
});
frappe.ui.form.on('Clearances', {
    purchase_order: function(frm) {
        if(cur_frm.doc.purchase_order){
            frappe.call({
                doc: frm.doc,
                method: "get_purchase_items",
                    callback: function(r) {
                    refresh_field("items");fix(frm);
                    }
            });
        }
	}
})

frappe.ui.form.on('Clearances', {
    purchase_taxes_and_charges_template: function(frm) {
		if(frm.doc.purchase_taxes_and_charges_template){
			frappe.call({
				doc: frm.doc,
				method: "get_purchase_taxes",
				    callback: function(r) {
                    refresh_field("taxes");fix(frm);
                    }
			});
		}
	}
})

frappe.ui.form.on("Clearances", "before_submit", function(frm, cdt, cdn) {
    $.each(frm.doc.items || [], function(i, d) {
        if (d.current_qty == 0){
            frappe.throw("يرجاء إدخال الكمية الحالية");
        }
    });
    $.each(frm.doc.taxes || [], function(i, d) {
        if (d.tax_amount == 0){
            frappe.throw("يرجاء إدخال قيمة الضريبة");
        }
    });
});

frappe.ui.form.on("Clearances", "validate", function(frm, cdt, cdn) {

    $.each(frm.doc.items || [], function(i, d) {
        if (d.current_qty > d.qty){
            frappe.throw("الكمية الحالية لا يمكن أن تكون أكبر من كمية العقد");
        }
	else if  (!frm.doc.is_return && d.current_qty < 0)
 	{frappe.throw("الكمية الحالية لا يمكن أن تكون سلبية");
	} 
        else if ((d.current_qty + d.previous_qty) > d.qty){
            frappe.throw("الكمية الإجمالية لا يمكن أن تكون أكبر من كمية العقد");
        }
        else {
            $.each(frm.doc.items || [], function(i, d) {
                d.current_amount = d.current_qty * d.rate;
                d.current_progress = 100 * d.current_qty / d.qty;
                d.previous_progress = 100 * d.previous_qty / d.qty;
                d.completed_qty = d.current_qty + d.previous_qty;
                d.completed_amount = d.completed_qty * d.rate;
                d.completed_progress = 100 * d.completed_qty / d.qty;
                d.remaining_qty = d.qty - d.completed_qty;
                d.remaining_amount = d.remaining_qty * d.rate;
                d.remaining_progress = 100 * d.remaining_qty / d.qty;
            });
        }
    });
});


//frappe.ui.form.on("Clearances","validate", function(){
  //  for (var i = 0; i < cur_frm.doc.taxes.length; i++){
    //    cur_frm.doc.taxes[i].tax_amount = cur_frm.doc.taxes[i].rate * cur_frm.doc.total_current_amount / 100;
      //  cur_frm.doc.taxes[i].total = cur_frm.doc.taxes[i].tax_amount + cur_frm.doc.total_current_amount;
   // }
  //  cur_frm.refresh_field('taxes');
//});

frappe.ui.form.on('Payment Entry Deduction', 'type', function(frm,cdt,cdn) { fix(frm);});


frappe.ui.form.on('Payment Entry Deduction','percentage',  function(frm,cdt,cdn) {
if (frm.doc.gross) {
var gross = frm.doc.gross;}
else{var gross = 0;}
var item=locals[cdt][cdn];
frappe.model.set_value(cdt, cdn, "amount", gross * item.percentage / 100);
fix(frm);
  });  
frappe.ui.form.on('Payment Entry Deduction','amount',  function(frm,cdt,cdn) {
if (frm.doc.gross ) {var gross = frm.doc.gross;}else{var gross = 0;}
var item = locals[cdt][cdn];
if (gross == 0) { frappe.model.set_value(cdt,cdn,'percentage', 0 ); frappe.model.set_value(cdt,cdn,'amount', 0 );  } else{
frappe.model.set_value(cdt,cdn,'percentage',item.amount*100/gross);
console.log("gross");
console.log(gross);
console.log("item.amount");
console.log(item.amount)
frappe.model.set_value(cdt,cdn,'custom_c_percentage',item.amount/gross);
}
fix(frm);
});
frappe.ui.form.on('Payment Entry Deduction','include_tax',  function(frm,cdt,cdn) {
fix(frm);
});
frappe.ui.form.on('Clearance Items Table','current_qty',  function(frm,cdt,cdn) {
var d = locals[cdt][cdn];
		if (d.current_qty > d.qty){
		frappe.model.set_value(cdt,cdn,'current_qty',d.qty-d.previous_qty);
            frappe.throw("الكمية الحالية لا يمكن أن تكون أكبر من كمية العقد");
        }
        else if  ( d.current_qty < 0)
        {
	frappe.model.set_value(cdt,cdn,'current_qty',d.current_amount/d.rate);
	frappe.throw("الكمية الحالية لا يمكن أن تكون سلبية");
        } 
        else if ((d.current_qty + d.previous_qty) > d.qty){
	   frappe.model.set_value(cdt,cdn,'current_qty',d.current_amount/d.rate);
            frappe.throw("الكمية الإجمالية لا يمكن أن تكون أكبر من كمية العقد");
        }
else{
                d.current_amount = d.current_qty * d.rate;
                d.current_progress = 100 * d.current_qty / d.qty;
                d.previous_progress = 100 * d.previous_qty / d.qty;
                d.completed_qty = d.current_qty + d.previous_qty;
                d.completed_amount = d.completed_qty * d.rate;
                d.completed_progress = 100 * d.completed_qty / d.qty;
                d.remaining_qty = d.qty - d.completed_qty;
                d.remaining_amount = d.remaining_qty * d.rate;
                d.remaining_progress = 100 * d.remaining_qty / d.qty;
		frappe.model.set_value(cdt,cdn,'completed_amount',d.completed_amount);
		frappe.model.set_value(cdt,cdn,'current_amount',d.current_amount);
		//frappe.model.set_value(cdt,cdn,'previous_progress',d.previous_progress);
		frappe.model.set_value(cdt,cdn,'completed_qty',d.completed_qty);
		frappe.model.set_value(cdt,cdn,'completed_progress',d.completed_progress);
		frappe.model.set_value(cdt,cdn,'remaining_qty',d.remaining_qty);
                frappe.model.set_value(cdt,cdn,'remaining_amount',d.remaining_amount);
		frappe.model.set_value(cdt,cdn,'remaining_progress',d.remaining_progress);
fix(frm);}
});




function fix(frm){
	console.log("fixed");
	//	aa();
	var advance_rate =0;
        var initial_rate = 0;
        var total = 0;
        var gross = 0;
        var advance = 0;
        var retention =0;
        var vat = 0;
        var rate = 0;
        let total_percentage=0;
        var total_taxes_amount=0;
        let t=0;
        var total_amount_before_vat=0;
	if (frm.doc.taxes[0] ) { rate = frm.doc.taxes[0].rate ;}
        var total_deduction = 0;
        frm.doc.items.forEach(function(item){gross+=item.current_qty*item.rate;   });
        frm.set_value("gross",gross);
        refresh_field("gross");
        frm.doc.deductions_table.forEach(function(ded) {
            if (ded.include_tax ==0){
                advance += ded.amount;
                total_percentage+=parseFloat(ded.custom_c_percentage);
            }
            else{
                retention+=ded.amount;
            } 
			if (ded.type=="Advance"){
                advance_rate+=ded.percentage;
            }
			else{initial_rate+=ded.percentage; }
			});
    frm.doc.items.forEach(function(item){
        if(total_percentage){
            frappe.model.set_value('Clearance Items Table',item.name,'c_amount',(item.current_amount-(item.current_amount*total_percentage)))
        }else{
            frappe.model.set_value('Clearance Items Table',item.name,'c_amount',item.current_amount);
        }
        frappe.model.set_value('Clearance Items Table',item.name,'tax_rate',rate);
        frappe.model.set_value('Clearance Items Table',item.name,'tax_amount',((item.c_amount.toFixed(2)/100)*rate));
        frappe.model.set_value('Clearance Items Table',item.name,'total_amount',parseFloat(item.c_amount.toFixed(2))+parseFloat(item.tax_amount.toFixed(2)));
        total_taxes_amount+=item.c_amount+item.tax_amount;
        t+=item.c_amount;
        total_amount_before_vat+=item.c_amount;
    });
    console.log("!!!!!!!!!");
    console.log(t);
	frappe.model.set_value('Clearances',frm.doc.name,'initial_delivery_payment_insurance_rate',initial_rate);
	frappe.model.set_value('Clearances',frm.doc.name,'advanced_payment_insurance_rate',advance_rate);
    frappe.model.set_value('Clearances',frm.doc.name,'initial_delivery_payment_insurance_amount',initial_rate*total_amount_before_vat/100);
    frappe.model.set_value('Clearances',frm.doc.name,'advanced_payment_insurance_amount',advance_rate*total_amount_before_vat/100); 

	frm.set_value("advance_payment",advance);
        refresh_field("advance_payment");
        frm.set_value("retention" ,retention);
        refresh_field("retention");
        frm.set_value("total_amount_before_vat",total_amount_before_vat);
        // frm.set_value("total_amount_before_vat",gross-advance);
        refresh_field("total_amount_before_vat");
        frm.doc.taxes.forEach(function(t) { vat += (total_amount_before_vat)*rate/100; frappe.model.set_value('Clearance Taxes Table',t.name,'tax_amount',(total_amount_before_vat)*rate/100); }); 
        // frm.doc.taxes.forEach(function(t) { vat += (gross-advance)*rate/100; frappe.model.set_value('Clearance Taxes Table',t.name,'tax_amount',(gross-advance)*rate/100); }); 

        frm.set_value("vat",vat);
        refresh_field("vat");
        frm.set_value("net_amount",total_amount_before_vat+vat-retention);
	// frm.set_value("net_amount",gross-advance+vat-retention);
        refresh_field("net_amount");
	// frm.set_value("total_current_amount",gross);
    frm.set_value("total_current_amount",total_amount_before_vat);
        refresh_field("total_current_amount");
	// frm.set_value("total_paid_amount",gross-advance+vat-retention);
    frm.set_value("total_paid_amount",total_amount_before_vat+vat-retention);
        refresh_field("total_paid_amount");
    frm.set_value("total_taxes_amount",total_taxes_amount);
	// frm.set_value("total_taxes_amount", vat + gross- advance );
        refresh_field("total_taxes_amount");

}
frappe.ui.form.on("Clearances", {
    validate:function(frm, cdt, cdn){
        /*var total = 0;
	var gross = 0;
	var advance = 0;
	var retention =0;
	var vat = 0;
	var rate = frm.doc.taxes[0].rate;
	var total_deduction = 0;
	frm.doc.items.forEach(function(item){gross+=item.rate*item.current_qty;   });
	frm.set_value("gross",gross);
	refresh_field("gross");
	frm.doc.deductions_table.forEach(function(ded) {if (ded.include_tax ==0 && rate >0){advance += ded.amount;}else{retention+=ded.amount;} });
	frm.set_value("advance_payment",advance);
	refresh_field("advance_payment");
	frm.set_value("retention" ,retention);
	refresh_field("retention");
	frm.set_value("total_amount_before_vat",gross-advance);
	refresh_field("total_amount_before_vat");
	frm.doc.taxes.forEach(function(t) { vat += (gross-advance)*rate/100;frappe.model.set_value('Clearance Taxes Table',t.name,'tax_amount',(gross-advance)*rate/100); }); 
	frm.set_value("vat",vat);
	refresh_field("vat");
	frm.set_value("net_amount",gross-advance+vat-retention);
	refresh_field("net_amount");
	frm.set_value("total_paid_amount",gross-advance+vat-retention);
        refresh_field("total_paid_amount");
	frm.set_value("total_taxes_amount", vat + gross- advance );
        refresh_field("total_taxes_amount");  
*/
fix(frm);
    },

    refresh: function(frm) {
    if (cur_frm.doc.docstatus == 1 && cur_frm.doc.total_paid_amount < (cur_frm.doc.total_current_amount - cur_frm.doc.total_deduction_amount - cur_frm.doc.advanced_payment_insurance_amount - cur_frm.doc.initial_delivery_payment_insurance_amount)){
    frm.add_custom_button(__("Make Payment"), function() {
           frm.refresh();
		   frappe.call({
				doc: frm.doc,
				method: "make_payment",
			});
			frappe.msgprint("تم إنشاء قيد الدفع بنجاح ... برجاء الدخول على القيد وتوجيه حساب الدفع والمبلغ المدفوع");
		},
		).addClass("btn-primary").css({'color':'white'});
fix(frm);	}}
});

frappe.ui.form.on("Clearances", {
    before_submit:function(frm, cdt, cdn){
        var dw = locals[cdt][cdn];
        var total = 0;
        frm.doc.deductions_table.forEach(function(dw) { total += dw.amount; });
        frm.set_value("total_deduction_amount", total);
        refresh_field("total_deduction_amount");
       // if (cur_frm.doc.total_deduction_amount > cur_frm.doc.total_taxes_amount){
        //    frappe.throw("مبلغ الخصومات لا يمكن أن يكون أكبر من المبلغ الإجمالي");
        //}
    },
});

frappe.ui.form.on("Clearances","validate", function(){
	//fix(frm);
        //cur_frm.doc.advanced_payment_insurance_amount = cur_frm.doc.total_taxes_amount * cur_frm.doc.advanced_payment_insurance_rate / 100;
        //cur_frm.doc.initial_delivery_payment_insurance_amount = cur_frm.doc.total_taxes_amount * cur_frm.doc.initial_delivery_payment_insurance_rate / 100;
});
