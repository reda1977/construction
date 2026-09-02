# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, json
from frappe.model.document import Document
from frappe import _
from frappe.desk.search import sanitize_searchfield
from frappe.utils import (flt, getdate, get_url, now,
nowtime, get_time, today, get_datetime, add_days)
from frappe.utils import add_to_date, now, nowdate

@frappe.whitelist()
def update_clearance_on_submit(doc, method=None):
	if doc.reference_doctype == "Clearances" and doc.clearance_payment:
		current = frappe.db.get_value("Clearances", doc.reference_link, "total_paid_amount")
		new = current + doc.total_debit
		frappe.db.set_value('Clearances', doc.reference_link, 'total_paid_amount', new)

@frappe.whitelist()
def update_clearance_on_cancel(doc, method=None):
	if doc.reference_doctype == "Clearances" and doc.clearance_payment:
		current = frappe.db.get_value("Clearances", doc.reference_link, "total_paid_amount")
		new = current - doc.total_debit
		frappe.db.set_value('Clearances', doc.reference_link, 'total_paid_amount', new)

@frappe.whitelist()
def cancel_clearance_on_je_cancel(doc, method=None):
	if doc.reference_link and frappe.db.exists('Clearances',doc.reference_link):
		clearance = frappe.get_doc('Clearances', doc.reference_link)
		if doc.reference_doctype == "Clearances" and not doc.clearance_payment:
			try:
				clearance.cancel()
			except:
				return("")
