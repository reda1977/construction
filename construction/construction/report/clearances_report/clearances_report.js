// Copyright (c) 2016, ERP Cloud Systems and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Clearances Report"] = {
	"filters": [
	    {
			"fieldname":"from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"width": "80"
		},
		{
			"fieldname":"to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"width": "80"
		},
		{
			"fieldname":"sales_order",
			"label": __("Sales Order"),
			"fieldtype": "Link",
			"options": "Sales Order",
		},
		{
			"fieldname":"purchase_order",
			"label": __("Purchase Order"),
			"fieldtype": "Link",
			"options": "Purchase Order",
		},
		{
			"fieldname":"clearance_no)",
			"label": __("Clearance No"),
			"fieldtype": "Data",
		},
		{
			"fieldname":"clearance_name",
			"label": __("Clearance Name"),
			"fieldtype": "Data",
		},
		{
			"fieldname":"clearance_type",
			"label": __("Clearance Type"),
			"fieldtype": "Select",
			"options":  ["Incoming","Outgoing"],
		},
		{
			"fieldname":"project",
			"label": __("Project"),
			"fieldtype": "Link",
			"options": "Projects",
		},
	]
};
