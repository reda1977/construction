# Copyright (c) 2013, erpcloud.systems and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _

def execute(filters=None):
	columns, data = [], []
	columns=get_columns()
	data=get_data(filters,columns)
	return columns, data

def get_columns():
	return [
		{
			"label": _("Clearance"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Clearances",
			"width": 120
		},
		{
			"label": _("Clearance Date "),
			"fieldname": "clearance_date",
			"fieldtype": "Date",
			"width": 120
		},
		{
			"label": _("Clearance No"),
			"fieldname": "clearance_no",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"label": _("Clearance Name"),
			"fieldname": "clearance_name",
			"fieldtype": "Data",
			"width": 300
		},
		{
			"label": _("Clearance Type"),
			"fieldname": "clearance_type",
			"fieldtype": "Data",
			"width": 110
		},
		{
			"label": _("Party Name"),
			"fieldname": "party",
			"fieldtype": "Data",
			"width": 140
		},
		{
			"label": _("Order No"),
			"fieldname": "order_no",
			"fieldtype": "Data",
			"width": 160
		},
		{
			"label": _("Order Date"),
			"fieldname": "order_date",
			"fieldtype": "Date",
			"width": 100
		},
		{
			"label": _("Project"),
			"fieldname": "project",
			"fieldtype": "Link",
			"options": "Project",
			"width": 100
		},
		{
			"label": _("Total Amount After Tax"),
			"fieldname": "total_taxes_amount",
			"fieldtype": "Currency",
			"width": 150
		},
		{
			"label": _("Total Current Amount"),
			"fieldname": "total_current_amount",
			"fieldtype": "Currency",
			"width": 260
		},
		{
			"label": _("Total Deduction Amount"),
			"fieldname": "total_deduction_amount",
			"fieldtype": "Currency",
			"width": 160
		},
		{
			"label": _("Advanced Payment Insurance Amount"),
			"fieldname": "advanced_payment_insurance_amount",
			"fieldtype": "Currency",
			"width": 200
		},
		{
			"label": _("Initial Delivery Payment Insurance Amount"),
			"fieldname": "initial_delivery_payment_insurance_amount",
			"fieldtype": "Currency",
			"width": 270
		},
		{
			"label": _("Total Paid Amount"),
			"fieldname": "total_paid_amount",
			"fieldtype": "Currency",
			"width": 150
		}
	]

def get_data(filters, columns):
	item_price_qty_data = []
	item_price_qty_data = get_item_price_qty_data(filters)
	return item_price_qty_data

def get_item_price_qty_data(filters):
	conditions = ""
	if filters.get("sales_order"):
		conditions += " and a.sales_order=%(sales_order)s"
	if filters.get("purchase_order"):
		conditions += " and a.purchase_order=%(purchase_order)s"
	if filters.get("clearance_type"):
		conditions += " and a.clearance_type=%(clearance_type)s"
	if filters.get("from_date"):
		conditions += " and a.clearance_date>=%(from_date)s"
	if filters.get("to_date"):
		conditions += " and a.clearance_date<=%(to_date)s"
	if filters.get("project"):
		conditions += " and a.project=%(project)s"
	if filters.get("clearance_no"):
		conditions += " and a.clearance_no=%(clearance_no)s"
	if filters.get("clearance_name"):
		conditions += " and a.clearance_name=%(clearance_name)s"
	item_results = frappe.db.sql("""
				select
						a.name as name,
						a.clearance_date as clearance_date,
						a.clearance_no as clearance_no,
						a.clearance_type as clearance_type,
						a.clearance_name as clearance_name,
						CONCAT_WS('',a.customer,a.supplier) as party,
						CONCAT_WS('',a.sales_order,a.purchase_order) as order_no,
						CONCAT_WS('',a.sales_order_date,a.purchase_order_date) as order_date,
						a.project as project,
						a.initial_delivery_payment_insurance_amount as initial_delivery_payment_insurance_amount,
						a.advanced_payment_insurance_amount as advanced_payment_insurance_amount,
						a.total_taxes_amount as total_taxes_amount,
						a.total_current_amount as total_current_amount,
						a.total_deduction_amount as total_deduction_amount,
						a.total_paid_amount as total_paid_amount						
				from `tabClearances` a 
				where
					 a.docstatus = 1
					{conditions}
				""".format(conditions=conditions), filters, as_dict=1)


	#price_list_names = list(set([item.price_list_name for item in item_results]))

	#buying_price_map = get_price_map(price_list_names, buying=1)
	#selling_price_map = get_price_map(price_list_names, selling=1)

	result = []
	if item_results:
		for item_dict in item_results:
			data = {
				'name': item_dict.name,
				'clearance_date': item_dict.clearance_date,
				'clearance_no': item_dict.clearance_no,
				'clearance_type': item_dict.clearance_type,
				'clearance_name': item_dict.clearance_name,
				'party': item_dict.party,
				'order_no': item_dict.order_no,
				'order_date': item_dict.order_date,
				'project': item_dict.project,
				'initial_delivery_payment_insurance_amount': item_dict.initial_delivery_payment_insurance_amount,
				'advanced_payment_insurance_amount': item_dict.advanced_payment_insurance_amount,
				'total_taxes_amount': item_dict.total_taxes_amount,
				'total_current_amount': item_dict.total_current_amount,
				'total_deduction_amount': item_dict.total_deduction_amount,
				'total_paid_amount': item_dict.total_paid_amount,
			}
			result.append(data)

	return result

def get_price_map(price_list_names, buying=0, selling=0):
	price_map = {}

	if not price_list_names:
		return price_map

	rate_key = "Buying Rate" if buying else "Selling Rate"
	price_list_key = "Buying Price List" if buying else "Selling Price List"

	filters = {"name": ("in", price_list_names)}
	if buying:
		filters["buying"] = 1
	else:
		filters["selling"] = 1

	pricing_details = frappe.get_all("Item Price",
		fields = ["name", "price_list", "price_list_rate"], filters=filters)

	for d in pricing_details:
		name = d["name"]
		price_map[name] = {
			price_list_key :d["price_list"],
			rate_key :d["price_list_rate"]
		}

	return price_map
