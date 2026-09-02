from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
import frappe, json
from frappe.model.document import Document
from frappe import _
from frappe.desk.search import sanitize_searchfield
from frappe.utils import (flt,rounded, getdate, get_url, now,
	nowtime, get_time, today, get_datetime, add_days)
from frappe.utils import add_to_date, now, nowdate
from frappe.model.document import Document
from frappe.utils import get_datetime, time_diff_in_hours
from frappe import _
import uuid,base64,os,requests,random
import math
from io import BytesIO
from pyqrcode import create as qr_create
from hashlib import sha256
from datetime import datetime
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from zatca.qr import qr_code
import lxml.etree as ET
class Clearances(Document):
	simple_invoice="assets/zatca/templates/simple_invoice.xml"
	standard_invoice="assets/zatca/templates/standard_invoice.xml"
	item_line="assets/zatca/templates/item_line.xml"
	extensions="assets/zatca/templates/extensions.xml"
	qr_code="assets/zatca/templates/qr_code.xml"
	site= frappe.local.site_path


	@frappe.whitelist()
	def on_submit(self):
		self.make_journal_entry()
		if self.sales_order:
			self.update_so_item_on_submit()
		elif self.purchase_order:
			self.update_po_item_on_submit()

		company=frappe.get_doc("Company",self.company)
		if  company.custom_zatca_status!="Disabled" and company.generate_xml_on_submit:
			self.first_xml(False)
			if self.simple and company.custom_zatca_status!="Disabled" and company.report_simple_invoices_on_submit:
				self.report(show_alert=True)
			if not self.simple and  company.custom_zatca_status!="Disabled" and company.clears_standard_invoices_on_submit:
				self.clearance(show_alert=True)
	@frappe.whitelist()
	def on_cancel(self):
		if self.sales_order:
			self.update_so_item_on_cancel()
		elif self.purchase_order:
			self.update_po_item_on_cancel()

	@frappe.whitelist()
	def make_journal_entry(self):
		total_debit=0
		total_credit=0
		receivable_advanced_payments_account = frappe.db.get_value("Company", self.company, "receivable_advanced_payments_account")
		third_party_insurances_account = frappe.db.get_value("Company", self.company, "third_party_insurances_account")
		payable_advanced_payments_account = frappe.db.get_value("Company", self.company, "payable_advanced_payments_account")
		insurances_for_others_account = frappe.db.get_value("Company", self.company, "insurances_for_others_account")
		default_receivable_account = frappe.db.get_value("Company", self.company, "default_receivable_account")
		default_payable_account = frappe.db.get_value("Company", self.company, "default_payable_account")
		default_income_account = frappe.db.get_value("Company", self.company, "default_income_account")
		default_expense_account = frappe.db.get_value("Company", self.company, "default_expense_account")
		default_cost_center = frappe.db.get_value("Company", self.company, "cost_center")
		if self.cost_center:
			default_cost_center=self.cost_center
		elif not default_cost_center and self.project:
			# Company has no default Cost Center configured. Fall back to the
			# Project's Cost Center -- the same source already used elsewhere
			# in this doctype (e.g. deduction rows fetched from the PO/SO)
			# -- instead of silently posting the income/expense account
			# without one, which ERPNext's GL Entry validation rejects for
			# Profit and Loss accounts ("Missing Cost Center").
			default_cost_center = frappe.db.get_value("Project", self.project, "cost_center")
		if not default_cost_center:
			frappe.throw(_(
				"Cost Center is required to submit this Clearance. Please set a Cost Center "
				"on this Clearance, on Project {0}, or set a default Cost Center for Company {1}."
			).format(self.project, self.company))
		tax_account = ""
		tax_amount = 0
		values = frappe.db.sql("""select
											account_head as account_head,
											tax_amount as tax_amount
											from `tabClearance Taxes Table` where `tabClearance Taxes Table`.parent = %s
					""",self.name,as_dict=1)


		for y in values:
			tax_account = y.account_head
			tax_amount = y.tax_amount
		c_tax_amount=tax_amount
		
		tax_amount=round(self.vat,3)
		if self.clearance_type == "Outgoing":
			total_debit+=abs(round(self.net_amount,2))
			accounts = [
				{
					"doctype": "Journal Entry Account",
					"account": default_receivable_account,
					"party_type": "Customer",
					"party": self.customer,
					"project": self.project,
					"debit": abs(round(self.net_amount,2)) ,
					"credit": 0,
					"debit_in_account_currency": abs(round(self.net_amount,2)),
					"user_remark": self.name
				}]

			for d in self.deductions_table:
				if d.type=="Advance":
					total_debit+=abs(round(d.amount,2))
					accounts.append(
					{
						"doctype": "Journal Entry Account",
						"account": d.account,
						
						"project": self.project,
						"debit": abs(round(d.amount,2)),
						"credit": 0,
						"debit_in_account_currency": abs(round(d.amount,2)), 
						"user_remark": self.name
					})

				else:
					total_debit+=abs(round(d.amount,2))
					accounts.append(
					{
					"doctype": "Journal Entry Account",
					"account": d.account,
					"project": self.project,
					"debit": abs(round(d.amount,2)), 
					"credit": 0,
					"debit_in_account_currency":abs(round(d.amount,2)),
					"user_remark": self.name
					})
			total_credit+=abs(round(self.gross,2))
			accounts.append(
				{
					"doctype": "Journal Entry Account",
					"account": default_income_account,
					"project": self.project,
					"debit": 0,
					"credit":abs(round(self.gross,2)),
					"credit_in_account_currency":abs(round(self.gross,2)),
					"user_remark": self.name,
					"cost_center": default_cost_center
				})
			total_credit+=abs(round(c_tax_amount,2))
			accounts.append(
				{
					"doctype": "Journal Entry Account",
					"account": tax_account,
					"project": self.project,
					"debit": 0,
					"credit": abs(round(c_tax_amount,2)),
					"credit_in_account_currency": abs(round(c_tax_amount,2)),
					"user_remark": self.name
				})
			# Compare rounded totals (not raw floats): summing many already-rounded
			# amounts can leave floating point dust (e.g. 1e-13) that makes
			# `total_debit != total_credit` true even though the real difference
			# is zero SAR. That used to add a spurious round-off row with an
			# amount that rounds to 0.00, which ERPNext's Journal Entry
			# validation correctly rejects ("Both Debit and Credit values
			# cannot be zero"). Rounding the difference before comparing/using
			# it fixes both the false positive and the row's amount.
			rounding_diff = round(total_debit - total_credit, 2)
			if rounding_diff != 0:
				round_off_account = frappe.db.get_value("Company", self.company, "round_off_account")
				if not round_off_account:
					frappe.throw(_("Please set a Round Off Account for company {0} to submit this Clearance (there is a rounding difference of {1}).").format(self.company, rounding_diff))
				if rounding_diff>0:
					accounts.append({
					"doctype": "Journal Entry Account",
					"account": round_off_account,
					"project": self.project,
					"debit": 0,
					"credit": rounding_diff,
					"credit_in_account_currency": rounding_diff,
					"user_remark": self.name
				})
				else:
					accounts.append({
						"doctype": "Journal Entry Account",
						"account": round_off_account,
						"project": self.project,
						"debit": abs(rounding_diff),
						"credit":0,
						"debit_in_account_currency": abs(rounding_diff),
						"user_remark": self.name
					})

						
			doc = frappe.get_doc({
				"doctype": "Journal Entry",
				"voucher_type": "Journal Entry",
				"company": self.company,
				"posting_date": self.clearance_date,
				"reference_doctype": "Clearances",
				"reference_link": self.name,
				"accounts": accounts,
				"cheque_no": self.name,
				"cheque_date": self.clearance_date,
				"user_remark": self.notes1,
				"remark": _('Clearance  {0}').format(self.name)

			})
			doc.insert()
			doc.submit()

		if self.clearance_type == "Incoming":
			accounts = [
				{
					"doctype": "Journal Entry Account",
					"account": default_expense_account,
					"project": self.project,
					"credit": 0,
					"debit": abs(round(self.gross,3)), 
					"debit_in_account_currency":round( self.gross,3),
					"user_remark": self.name,
					"cost_center": default_cost_center
				}]
			for d in self.deductions_table:
				if d.type == "Advance":
					accounts.append(
					{
						"doctype": "Journal Entry Account",
						"account": d.account,
						"project": self.project,
						"credit": abs(round(d.amount,3)),
						"debit": 0,
						"credit_in_account_currency": round(d.amount,3),
						"user_remark": self.name
					})
				else:
					accounts.append(
					{
						"doctype": "Journal Entry Account",
						"account": d.account,
						"project": self.project,
						"credit": abs(round(d.amount,3)),
						"debit": 0,
						"credit_in_account_currency": round(d.amount,3),
						"user_remark": self.name
					})
			accounts.append(
				{
					"doctype": "Journal Entry Account",
					"account": default_payable_account,
					"party_type" : "Supplier",
					"party": self.supplier,
					"project": self.project,
					"credit": abs(round(self.net_amount,3)),
					"debit": 0,
					"credit_in_account_currency": round(self.net_amount,3),
					"user_remark": self.name
				})
			accounts.append(
				{
					"doctype": "Journal Entry Account",
					"account": tax_account,
					"project": self.project,
					"debit": abs(round(tax_amount,3)),
					"credit": 0,
					"debit_in_account_currency": round(tax_amount,3),
					"user_remark": self.name
				})
			doc = frappe.get_doc({
				"doctype": "Journal Entry",
				"voucher_type": "Journal Entry",
				"company": self.company,
				"reference_doctype": "Clearances",
				"reference_link": self.name,
				"posting_date": self.clearance_date,
				"accounts": accounts,
				"cheque_no": self.name,
				"cheque_date": self.clearance_date,
				"user_remark": self.notes,
				"remark": _('Clearance  {0}').format(self.name)

			})
			doc.insert()
			doc.submit()

	@frappe.whitelist()
	def get_purchase_items(self):
		process = frappe.get_doc("Purchase Order", self.purchase_order)
		if process:
			if process.items:
				self.add_po_item_in_table(process.items, "items")

	@frappe.whitelist()
	def get_purchase_taxes(self):
		process = frappe.get_doc("Purchase Taxes and Charges Template", self.purchase_taxes_and_charges_template)
		if process:
			if process.taxes:
				self.add_po_taxes_in_table(process.taxes, "taxes")

	@frappe.whitelist()
	def get_sales_items(self):
		process = frappe.get_doc("Sales Order", self.sales_order)
		if process:
			if process.items:
				self.add_so_item_in_table(process.items, "items")

	@frappe.whitelist()
	def get_sales_taxes(self):
		process = frappe.get_doc("Sales Taxes and Charges Template", self.sales_taxes_and_charges_template)
		if process:
			if process.taxes:
				self.add_so_taxes_in_table(process.taxes, "taxes")

	@frappe.whitelist()
	def add_po_item_in_table(self, table_value, table_name):
		self.set(table_name, [])
		for item in table_value:
			po_item = self.append(table_name, {})
			po_item.name1 = item.name
			po_item.item_code = item.item_code
			po_item.item_name = item.item_name
			po_item.description = item.description
			po_item.uom = item.uom
			po_item.qty = item.qty
			po_item.rate = item.rate
			po_item.amount = item.amount
			po_item.previous_qty = item.current_qty
			po_item.previous_amount = item.current_amount
			cq=0
			cq = 0
			try :
				last = frappe.get_last_doc('Clearances', filters= {'purchase_order': self.purchase_order})
				for i in last.items:
					if i.item_code == item.item_code :
						cq = i.completed_qty
						ca = i.completed_amount
				po_item.previous_qty = cq
				po_item.previous_amount = ca
				po_item.current_qty = item.qty - cq
				po_item.current_amount = item.amount - ca
				po_item.completed_amount = item.qty
				po_item.completed_amount = item.amount
			except:
				po_item.previous_qty = 0
				po_item.previous_amount = 0
				po_item.current_qty = item.qty
				po_item.current_amount = item.amount
				po_item.compeled_qty = item.qty
				po_item.completed_amount = item.amount

	def validate(self):
		self.sync_taxes_and_item_tax_rate()
		# total_current_amount=0
		# total_c_percentage=0
		# for item in self.items:
		# 	total_current_amount=total_current_amount+item.current_amount
		# 	item.c_amount=item.current_amount

		# for deduction in self.deductions_table:
		# 	if deduction.include_tax==0:
		# 		percentage=(deduction.amount/total_current_amount)*100
		# 		deduction.custom_c_percentage=percentage
		# 		total_c_percentage=total_c_percentage+deduction.custom_c_percentage
		# 	else:
		# 		percentage=(deduction.amount/total_current_amount)*100
		# 		deduction.custom_c_percentage=percentage
		
		# if total_c_percentage>0:
		# 	total_c_percentage=round(total_c_percentage, 2)
		# 	print(total_c_percentage)
		# 	for item in self.items:
		# 		_amount=(item.c_amount*total_c_percentage)/100
		# 		item.c_amount=round(item.c_amount-_amount,4)


		#this code to set tax_rate for each item for zatca and Callcualte Tax Amount for Zatca
		#################################################
		# if self.taxes:
		# 	tax_rate=self.taxes[0].rate
		# else:
		# 	tax_rate=15
		# for item in self.items:
		# 	item.tax_rate=tax_rate
		# 	item.tax_amount=round((item.c_amount/100)*item.tax_rate,2)
		#Callcualte Tax Amount for Zatca



	def sync_taxes_and_item_tax_rate(self):
		"""
		Server-side safety net for the tax rate/amount that clearances.js
		normally computes client-side (function fix()).

		This app was submitting invoices where the "Clearance Taxes Table"
		child table was empty even though "Sales/Purchase Taxes and Charges
		Template" was set on the document (e.g. because the template was
		selected before the linked Sales/Purchase Order populated the items,
		or the field's on-change handler simply never re-fired for that
		session). Every item's tax_rate/tax_amount then silently stayed at 0,
		which either produced a wrong (untaxed) ZATCA invoice, or blocked
		submission entirely with "item ... is missing vat category as it's
		zero taxed." from before_submit().

		This does not touch item.c_amount (the taxable base after
		deductions) - that is still computed by clearances.js. It only makes
		sure the tax rate that's supposed to apply is actually applied,
		regardless of whether the browser-side script ran.
		"""
		if self.clearance_type == "Outgoing":
			template_doctype = "Sales Taxes and Charges Template"
			template_name = self.sales_taxes_and_charges_template
		elif self.clearance_type == "Incoming":
			template_doctype = "Purchase Taxes and Charges Template"
			template_name = self.purchase_taxes_and_charges_template
		else:
			return

		if not template_name:
			return

		if not self.taxes:
			template = frappe.get_cached_doc(template_doctype, template_name)
			for tax in template.taxes:
				self.append("taxes", {
					"charge_type": tax.charge_type,
					"account_head": tax.account_head,
					"description": tax.description,
					"rate": tax.rate,
					"tax_amount": 0,
					"total": 0,
				})

		if not self.taxes:
			return

		rate = flt(self.taxes[0].rate)

		for item in self.items:
			if flt(item.c_amount) == 0:
				continue
			if flt(item.tax_rate) != rate:
				item.tax_rate = rate
			expected_tax_amount = round((flt(item.c_amount) / 100) * rate, 2)
			if abs(flt(item.tax_amount) - expected_tax_amount) > 0.01:
				item.tax_amount = expected_tax_amount
				item.total_amount = round(flt(item.c_amount) + expected_tax_amount, 2)

	@frappe.whitelist()
	def add_po_taxes_in_table(self, table_value, table_name):
		self.set(table_name, [])
		for tax in table_value:
			po_tax = self.append(table_name, {})
			po_tax.charge_type = tax.charge_type
			po_tax.account_head = tax.account_head
			po_tax.description = tax.description
			po_tax.rate = tax.rate
			po_tax.tax_amount = tax.tax_amount
			po_tax.total = tax.total

	@frappe.whitelist()
	def add_so_item_in_table(self, table_value, table_name):
		self.set(table_name, [])
		for item in table_value:
			so_item = self.append(table_name, {})
			so_item.name1 = item.name
			so_item.item_code = item.item_code
			so_item.item_name = item.item_name
			so_item.description = item.description
			so_item.uom = item.uom
			so_item.qty = item.qty
			so_item.rate = item.rate
			so_item.amount = item.amount
			cq = 0
			cq = 0
			try:
				last = frappe.get_last_doc('Clearances', filters={'sales_order':self.sales_order})
				for i in last.items:
					if i.item_code== item.item_code:
						
						cq = i.completed_qty
						ca = i.completed_amount
				so_item.previous_qty = cq
				so_item.previous_amount = ca
				so_item.previous_progress= (cq/item.qty)*100
				so_item.current_qty = item.qty - cq
				so_item.current_amount =  item.amount-ca
				so_item.c_amount=so_item.current_amount
				so_item.current_progress=100-so_item.previous_progress
				so_item.completed_qty = item.qty 
				so_item.completed_amount = item.amount
				so_item.completed_progress = 100 
			except:
				so_item.previous_qty = 0
				so_item.previous_amount =  0
				so_item.previous_progress = 0
				so_item.current_qty = item.qty
				so_item.current_amount = item.amount
				so_item.c_amount=so_item.current_amount
				so_item.current_progress=100 
				so_item.completed_qty = item.qty
				so_item.completed_amount = item.amount
				so_item.completed_progress = 100



	@frappe.whitelist()
	def add_so_taxes_in_table(self, table_value, table_name):
		self.set(table_name, [])
		for tax in table_value:
			so_tax = self.append(table_name, {})
			so_tax.charge_type = tax.charge_type
			so_tax.account_head = tax.account_head
			so_tax.description = tax.description
			so_tax.rate = tax.rate
			so_tax.tax_amount = tax.tax_amount
			so_tax.total = tax.total

	@frappe.whitelist()
	def make_payment(self):

		default_receivable_account = frappe.db.get_value("Company", self.company, "default_receivable_account")
		default_payable_account = frappe.db.get_value("Company", self.company, "default_payable_account")
		default_cash_account = frappe.db.get_value("Company", self.company, "default_cash_account")

		if self.clearance_type == "Outgoing" and self.total_deduction_amount > 0:
			accounts = [
				{
					"doctype": "Journal Entry Account",
					"account": default_cash_account,
					"debit": 0,
					"project": self.project,
					"credit": round((round(self.total_taxes_amount, 2) + round(self.total_deduction_amount, 2) - round(self.advanced_payment_insurance_amount, 2) - round(self.initial_delivery_payment_insurance_amount, 2) - round(self.total_paid_amount, 2)), 2),
					"credit_in_account_currency": round((round(self.total_taxes_amount, 2) + round(self.total_deduction_amount, 2) - round(self.advanced_payment_insurance_amount, 2) - round(self.initial_delivery_payment_insurance_amount, 2) - round(self.total_paid_amount, 2)), 2),
					"user_remark": self.name
				},
				{
					"doctype": "Journal Entry Account",
					"account": default_receivable_account,
					"debit": round((round(self.total_taxes_amount, 2) - round(self.advanced_payment_insurance_amount, 2) - round(self.initial_delivery_payment_insurance_amount, 2) - round(self.total_paid_amount, 2)), 2),
					"party_type": "Customer",
					"party": self.customer,
					"project": self.project,
					"credit": 0,
					"debit_in_account_currency": round((round(self.total_taxes_amount, 2) - round(self.advanced_payment_insurance_amount, 2) - round(self.initial_delivery_payment_insurance_amount, 2) - round(self.total_paid_amount, 2)), 2),
					"user_remark": self.name
				}
			]
			deductions_table = frappe.db.sql(""" select 
			account as account ,
			amount as amount,
			description as description,
			cost_center as cost_center
			from `tabPayment Entry Deduction` where parent = %s
			""",self.name,as_dict=1)

			for x in deductions_table:
				accounts1 = {
					"doctype": "Journal Entry Account",
					"account": x.account,
					"debit": round(x.amount, 2),
					"project": self.project,
					"cost_center": x.cost_center,
					"credit": 0,
					"debit_in_account_currency": round(x.amount, 2),
					"user_remark": x.description
				},
				accounts.extend(accounts1)

			doc = frappe.get_doc({
				"doctype": "Journal Entry",
				"voucher_type": "Journal Entry",
				"clearance_payment": 1,
				"company": self.company,
				"reference_doctype": "Clearances",
				"reference_link": self.name,
				"posting_date": self.clearance_date,
				"accounts": accounts,
				"cheque_no": self.name,
				"cheque_date": self.clearance_date,
				"user_remark": self.notes,
				"remark": _('Clearance  {0}').format(self.name)
					})
			doc.insert()

		if self.clearance_type == "Outgoing" and self.total_deduction_amount == 0:
			accounts = [
				{
					"doctype": "Journal Entry Account",
					"account": default_receivable_account,
					"debit": round((round(self.total_taxes_amount, 2) - round(self.advanced_payment_insurance_amount, 2) - round(self.initial_delivery_payment_insurance_amount, 2) - round(self.total_paid_amount, 2)), 2),
					"party_type": "Customer",
					"party": self.customer,
					"project": self.project,
					"credit": 0,
					"debit_in_account_currency": round((round(self.total_taxes_amount, 2) - round(self.advanced_payment_insurance_amount, 2) - round(self.initial_delivery_payment_insurance_amount, 2) - round(self.total_paid_amount, 2)), 2),
					"user_remark": self.name
				},
				{
					"doctype": "Journal Entry Account",
					"account": default_cash_account,
					"debit": 0,
					"project": self.project,
					"credit": round((round(self.total_taxes_amount, 2) - round(self.advanced_payment_insurance_amount, 2) - round(self.initial_delivery_payment_insurance_amount, 2) - round(self.total_paid_amount, 2)), 2),
					"credit_in_account_currency": round((round(self.total_taxes_amount, 2) - round(self.advanced_payment_insurance_amount, 2) - round(self.initial_delivery_payment_insurance_amount, 2) - round(self.total_paid_amount, 2)), 2),
					"user_remark": self.name
				}
			]

			doc = frappe.get_doc({
				"doctype": "Journal Entry",
				"voucher_type": "Journal Entry",
				"clearance_payment": 1,
				"company": self.company,
				"reference_doctype": "Clearances",
				"reference_link": self.name,
				"posting_date": self.clearance_date,
				"accounts": accounts,
				"cheque_no": self.name,
				"cheque_date": self.clearance_date,
				"user_remark": self.notes,
				"remark": _('Clearance  {0}').format(self.name)
					})
			doc.insert()

		if self.clearance_type == "Incoming" and self.total_deduction_amount > 0:
			accounts = [
				{
					"doctype": "Journal Entry Account",
					"account": default_cash_account,
					"project": self.project,
					"debit": round((round(self.total_taxes_amount, 2) + round(self.total_deduction_amount, 2) - round(self.advanced_payment_insurance_amount, 2) - round(self.initial_delivery_payment_insurance_amount, 2) - round(self.total_paid_amount, 2)), 2),
					"credit": 0,
					"debit_in_account_currency": round((round(self.total_taxes_amount, 2) + round(self.total_deduction_amount, 2) - round(self.advanced_payment_insurance_amount, 2) - round(self.initial_delivery_payment_insurance_amount, 2) - round(self.total_paid_amount, 2)), 2),
					"user_remark": self.name
				},
				{
					"doctype": "Journal Entry Account",
					"account": default_payable_account,
					"party_type": "Supplier",
					"party": self.supplier,
					"project": self.project,
					"debit": 0,
					"credit": round((round(self.total_taxes_amount, 2) - round(self.advanced_payment_insurance_amount, 2) - round(self.initial_delivery_payment_insurance_amount, 2) - round(self.total_paid_amount, 2)) ,2),
					"credit_in_account_currency": round((round(self.total_taxes_amount, 2) - round(self.advanced_payment_insurance_amount, 2) - round(self.initial_delivery_payment_insurance_amount, 2) - round(self.total_paid_amount, 2)) ,2),
					"user_remark": self.name
				}
			]
			deductions_table = frappe.db.sql(""" select 
			account as account ,
			amount as amount,
			description as description,
			cost_center as cost_center
			from `tabPayment Entry Deduction` where parent = %s
			""", self.name, as_dict=1)

			for x in deductions_table:
				accounts1 = {
					"doctype": "Journal Entry Account",
					"account": x.account,
					"credit": round(x.amount, 2),
					"project": self.project,
					"cost_center": x.cost_center,
					"debit": 0,
					"credit_in_account_currency": round(x.amount, 2),
					"user_remark": x.description
				},
				accounts.extend(accounts1)

			doc = frappe.get_doc({
				"doctype": "Journal Entry",
				"voucher_type": "Journal Entry",
				"company": self.company,
				"reference_doctype": "Clearances",
				"reference_link": self.name,
				"clearance_payment": 1,
				"posting_date": self.clearance_date,
				"accounts": accounts,
				"cheque_no": self.name,
				"cheque_date": self.clearance_date,
				"user_remark": self.notes,
				"remark": _('Clearance  {0}').format(self.name)
					})
			doc.insert()

		if self.clearance_type == "Incoming" and self.total_deduction_amount == 0:
			accounts = [
				{
					"doctype": "Journal Entry Account",
					"account": default_cash_account,
					"project": self.project,
					"debit": round((round(self.total_taxes_amount, 2) - round(self.advanced_payment_insurance_amount, 2) - round(self.initial_delivery_payment_insurance_amount, 2) - round(self.total_paid_amount, 2)), 2),
					"credit": 0,
					"debit_in_account_currency": round((round(self.total_taxes_amount, 2) - round(self.advanced_payment_insurance_amount, 2) - round(self.initial_delivery_payment_insurance_amount, 2) - round(self.total_paid_amount, 2)), 2),
					"user_remark": self.name
				},
				{
					"doctype": "Journal Entry Account",
					"account": default_payable_account,
					"party_type": "Supplier",
					"party": self.supplier,
					"project": self.project,
					"debit": 0,
					"credit": round((round(self.total_taxes_amount, 2) - round(self.advanced_payment_insurance_amount,2) - round(self.initial_delivery_payment_insurance_amount, 2) - round(self.total_paid_amount, 2)), 2),
					"credit_in_account_currency": round((round(self.total_taxes_amount, 2) - round(self.advanced_payment_insurance_amount, 2) - round(self.initial_delivery_payment_insurance_amount, 2) - round(self.total_paid_amount, 2)), 2),
					"user_remark": self.name
				}
			]

			doc = frappe.get_doc({
				"doctype": "Journal Entry",
				"voucher_type": "Journal Entry",
				"company": self.company,
				"reference_doctype": "Clearances",
				"reference_link": self.name,
				"clearance_payment": 1,
				"posting_date": self.clearance_date,
				"accounts": accounts,
				"cheque_no": self.name,
				"cheque_date": self.clearance_date,
				"user_remark": self.notes,
				"remark": _('Clearance  {0}').format(self.name)
			})
			doc.insert()

	@frappe.whitelist()
	def update_so_item_on_submit(self):
		for x in self.items:
			frappe.db.set_value('Sales Order Item', x.name1, 'current_qty', x.completed_qty)
			frappe.db.set_value('Sales Order Item', x.name1, 'current_amount', x.completed_amount)


	@frappe.whitelist()
	def update_po_item_on_submit(self):
		for x in self.items:
			frappe.db.set_value('Purchase Order Item', x.name1, 'current_qty', x.completed_qty)
			frappe.db.set_value('Purchase Order Item', x.name1, 'current_amount', x.completed_amount)

	@frappe.whitelist()
	def update_so_item_on_cancel(self):
		for x in self.items:
			so_current_qty = frappe.db.get_value('Sales Order Item', x.name1, 'current_qty')
			so_current_amt = frappe.db.get_value('Sales Order Item', x.name1, 'current_amount')
			frappe.db.set_value('Sales Order Item', x.name1, 'current_qty', so_current_qty - x.current_qty)
			frappe.db.set_value('Sales Order Item', x.name1, 'current_amount', so_current_amt - x.current_amount)

	@frappe.whitelist()
	def update_po_item_on_cancel(self):
		for x in self.items:
			po_current_qty = frappe.db.get_value('Purchase Order Item', x.name1, 'current_qty')
			po_current_amt = frappe.db.get_value('Purchase Order Item', x.name1, 'current_amount')
			frappe.db.set_value('Purchase Order Item', x.name1, 'current_qty', po_current_qty - x.current_qty)
			frappe.db.set_value('Purchase Order Item', x.name1, 'current_amount', po_current_amt - x.current_amount)

	@frappe.whitelist()
	def vat_category(self):
		v=frappe.db.get_all("VAT category",filters={"default":1,"disabled":0})
		if v:
			self.custom_vat_category=v[0]["name"]

	
	def before_submit(self):
		self.zatca_status="Pending"
		ind=1
		for i in self.items:
			if i.tax_rate==0 and i.c_amount!=0 :
				if not i.custom_vat_category :
					frappe.throw(_("row {} , item {} is missing vat category as it's zero taxed.").format(ind,i.item_code))
				if (not i.is_zero_rated and not i.is_exempt):
					frappe.throw(_("row {} , item {} is zero taxed, select type (zero, exempted).").format(ind,i.item_code))
				if i.is_zero_rated and i.is_exempt:
					frappe.throw(_("row {} , item {} can't be zero ated and exempted at the same time.").format(ind,i.item_code))
			ind+=1
		self.custom_pih=""


	@frappe.whitelist()
	def first_xml(self,show_alert=True):
		company=frappe.get_doc("Company",self.company)
		if company.custom_zatca_status=="Disabled":
			alert(_("ZATCA is disabled"),"red")
			return
		if not self.uuid:
			self.uuid=str(uuid.uuid4())
			frappe.db.set_value("Clearances",self.name,"uuid",self.uuid)
		possible_warnings=False
		if self.simple:
			f=open(self.simple_invoice,"r")
			type_code_name="0200000"
		else:
			customer_tax_id,customer_address=self.validate_customer_details()
			f=open(self.standard_invoice,"r")
			type_code_name="0100000"
			if not customer_address or not customer_tax_id:
				possible_warnings=True
		xml=f.read()
		if not self.uuid:
			self.uuid=str(uuid.uuid4())
		links=frappe.db.get_all("Dynamic Link",filters={"link_doctype":"Company","link_name":self.company,"parenttype":"Address"},fields=["parent"])
		if len(links)>0:
			address=frappe.get_doc("Address",links[0]["parent"])
		else:
			frappe.throw(_("Address is missing for company {}").format(self.company))
		qr_code=""
		payment_means="10"
		country_code="SA"
		type_code="388"
		debit_credit_reason=""
		billing_reference=""
		delivery_date="""<cac:Delivery>
    	<cbc:ActualDeliveryDate>{0}</cbc:ActualDeliveryDate>
    </cac:Delivery>""".format(self.clearance_date)
		if self.is_return or self.is_debit_note:
			delivery_date=""
			if self.is_return:
				type_code="381"
			else:
				type_code="383"
				
			debit_credit_reason="<cbc:InstructionNote>"+self.custom_reason+"</cbc:InstructionNote>" if self.custom_reason else  "<cbc:InstructionNote>CANCELLATION_OR_TERMINATION</cbc:InstructionNote>"
			billing_reference="""
			<cac:BillingReference>
				<cac:InvoiceDocumentReference>
					<cbc:ID>{}</cbc:ID>
				</cac:InvoiceDocumentReference>
			</cac:BillingReference>
			""".format(self.return_against)
		crn=company.cr_number
		scheme_type="CRN"
		schemes={"Commercial Registration number":"CRN","MOMRAH license":"MOM","MHRSD license":"MLS","700 Number":"700","MISA license":"SAG","Other OD":"OTH"}
		if company.custom_scheme:
			scheme_type=schemes[company.custom_scheme]
		try:
			seconds=self.posting_time.seconds
		except:
			seconds=frappe.utils.get_timedelta(self.posting_time).seconds
		h=str(seconds//3600)
		h="0"+h if len(h) ==1 else h
		m=str((seconds%3600)//60)
		m="0"+m if len(m) ==1 else m
		s=str((seconds%3600)%60)
		s="0"+s if len(s) ==1 else s
		issue_time=h+":"+m+":"+s
		tax_id=company.tax_id
		taxable=0
		subtax="""<cac:TaxSubtotal>
            <cbc:TaxableAmount currencyID="{currency}">{taxable_amount_}</cbc:TaxableAmount>
            <cbc:TaxAmount currencyID="{currency}">{tax_amount}</cbc:TaxAmount>
             <cac:TaxCategory>
                 <cbc:ID >{tax_category}</cbc:ID>
                 <cbc:Percent>{vat_percent}</cbc:Percent>
                 {tax_code}
            	 {tax_reason}
                <cac:TaxScheme>
                   <cbc:ID >VAT</cbc:ID>
                </cac:TaxScheme>
             </cac:TaxCategory>

        </cac:TaxSubtotal>""".replace("{currency}",self.currency)
		tax15=0
		taxes15=0
		taxzero=0
		subtaxes=""
		zero=0
		zerocode=""
		exempt=0
		exemptcode=""
		total_before_vat=0
		total_vat=0
		for i in self.items:
			if i.tax_rate!=0:
				taxable+=round(i.c_amount,2)
			if i.tax_rate==15:
				tax15+=round(i.c_amount,2)
				taxes15+=round(i.tax_amount,2)
			if i.tax_rate==0 :
				if i.is_zero_rated :
					zero+=round(i.c_amount,2)
					zerocode=i.custom_vat_category
				else:
					exemptcode=i.custom_vat_category
					exempt+=round(i.c_amount,2)
		if tax15 or (zero==0 and exempt==0):
			new=subtax.replace("{tax_category}","S").replace("{vat_percent}","15.00").replace("{taxable_amount_}",num(tax15)).replace("{tax_amount}",num(taxes15)).replace("{tax_code}","").replace("{tax_reason}","")
			subtaxes+=new
			
			total_before_vat+=truncate(tax15)
			#total_vat+=truncate(tax15*0.15)
			
		codes={"E":exempt,"Z":zero}
		for tax_category in codes:
			if codes[tax_category]==0:
				continue
			total_before_vat+=round(codes[tax_category],2)
			t=zerocode if tax_category=="Z" else exemptcode
			tax_code="<cbc:TaxExemptionReasonCode>"+str(t)+"</cbc:TaxExemptionReasonCode>"
			text=frappe.db.get_value("VAT category",t,"english_text")
			tax_reason="<cbc:TaxExemptionReason>"+str(text)+"</cbc:TaxExemptionReason>"
			
			new=subtax.replace("{tax_category}",tax_category).replace("{vat_percent}","0.00").replace("{taxable_amount_}",num(codes[tax_category]))
			new=new.replace("{tax_amount}","0.00").replace("{tax_code}",tax_code).replace("{tax_reason}",tax_reason)
			subtaxes+=new
		if self.custom_pih and self.custom_pih !="":
			pih=self.custom_pih
		else:
			pih=company.pih
		outstanding_total=round(self.total_amount_before_vat,2)
		
		lines,total_before_vat,total_vat=self.get_lines()
		#
		total_after_vat=total_before_vat+total_vat
		base_vat=num(total_vat*self.conversion_rate)
		#frappe.throw(str(total_after_vat))
		replace={"{id}":self.name,"{uuid}":self.uuid,"{issue_date}":self.clearance_date,"{issue_time}":issue_time,"{currency}":self.currency,
			"{pih}":pih,"{tax_currency}":"SAR","{qr_code}":qr_code,"{company_tax_id}":tax_id,"{company_name}":company.name,
			"{vat_percent}":num(self.items[0].tax_rate),"{total}":num(total_before_vat),"{total_discount}":num(0),"{tax_amount}":num(total_vat),
			"{taxable_amount}":num(total_before_vat),"{total_amount}":num(total_after_vat),"{total_advance}":num(0),
			"{payable_amount}":num(total_after_vat),"{payment_means}":payment_means,"{base_tax_amount}":base_vat,
			"{country_code}":country_code,"{scheme_type}":scheme_type,"{scheme_id}":crn,
			"{street_name}":address.address_line1,"{city_name}":address.city,"{postal_code}":address.pincode,"{building_number}":address.building_number,
			"{city_subdivision}":address.subdivision,"{plot}":address.plot,"{debit_credit_reason}":debit_credit_reason,
			"{billing_reference}":billing_reference,"{customer_name}":self.customer,"{delivery_date}":delivery_date,"{subtax}":subtaxes,"{rounding_amount}":round(0,2)
}		
		replace["{customer_scheme_id}"]= ""
		replace["{customer_id}"]=""
		replace["{customer_street_name}"]=address.address_line1 or ""
		replace["{customer_scheme}\n"]=""
		if not self.simple:
			replace["{customer_tax_id}"]=customer_tax_id or ''
			replace["{customer_street_name}"]=customer_address.address_line1 if customer_address else ""
			replace["{customer_building_number}"]=customer_address.building_number if customer_address else ""
			replace["{customer_plot}"]=customer_address.plot if customer_address else ""
			replace["{customer_city_subdivision}"]=customer_address.subdivision if customer_address else ""
			replace["{customer_city_name}"]=customer_address.city if customer_address else ""
			replace["{customer_postal_code}"]=customer_address.pincode if customer_address else ""
			if customer_address:
				a=customer_address
				possible_warnings= not a.address_line1 or not a.plot or not a.pincode or not a.subdivision or not a.city or not a.building_number
		replace["{type_code_name}"]=type_code_name
		replace["{type_code}"]=type_code
		xml=xml.replace("{invoice_lines}",lines)
		xml=replaceAll(xml,replace)
		if not self.simple:
			xml=xml.replace("{ext:UBLExtensions}","")
			xml=xml.replace("{QR}","")
		time=str(self.posting_time).replace(":","")[0:6]
		if time[-1]==".":
			time=time[:-2]+"0"+time[-2]
		new_name=company.tax_id+"_"+str(self.clearance_date).replace("-","")+"T"+time+"_"+self.name+".xml"
		if self.simple:
			self.validate_signature()
			xml=self.sign_invoice(company,xml,total_after_vat,total_vat)
			if not xml:
				self.xml_path=""
				alert("Error while Signing xml invoice.","red")
				return(False)
		if xml:
			if not self.xml_path:
				file_=frappe.get_doc({
					"doctype":"File",
					"is_private":1,
					"attached_to_doctype":"Clearances",
					"attached_to_name":self.name,
					"file_name":new_name,
					"content":xml.encode("utf-8")		
				})
				file_.save()
				self.xml_path=file_.file_url
				frappe.db.set_value("Clearances",self.name,"xml_path",file_.file_url)
			else:
				new_file=open(self.site+self.xml_path,"w")
				new_file.write(xml)
				new_file.close()
			if self.simple:
				if self.ksa_einv_qr:
					file_doc=frappe.get_all("File",{"file_url":self.ksa_einv_qr})
					if len(file_doc):
						frappe.delete_doc("File",file_doc[0]["name"])
				qr_image=BytesIO()
				url=qr_create(self.qr_code_text,error="L")
				url.png(qr_image,scale=2,quiet_zone=1)
				name=self.xml_path.split("/")[-1].replace("xml","png")
				_file=frappe.get_doc({
					"doctype":"File",
					"file_name":name,
					"is_private":0,
					"content":qr_image.getvalue(),
					"attached_to_doctype":"Clearances",
					"attached_to_name":self.name
				})
				_file.save()
				self.ksa_einv_qr=_file.file_url
				frappe.db.set_value("Clearances",self.name,"ksa_einv_qr",_file.file_url)
				frappe.db.set_value("Clearances",self.name,"qr_code_text",qr_code)
				self.qr_code_text=qr_code
		if not self.simple:
			cananolized_xml=cananolize(self.site+self.xml_path)
			if not cananolized_xml:
				alert("Error while canonicalizing xml invoice.","red")
				return(False)
			hash_=get_hash(cananolized_xml)
			self.hash=hash_
			frappe.db.set_value("Clearances",self.name,"hash",hash_)
			if show_alert:
				alert(_("Standard Invoice XML Created successfully."))
		if not self.custom_pih:
			self.custom_pih=pih
			frappe.db.set_value("Clearances",self.name,"custom_pih",pih)
			frappe.db.set_value("Company",company.name,"pih",self.hash,update_modified=False)
		#self.save(ignore_version=True)
		comment(self.name,_("XML Created successfully."))
		if possible_warnings:
			alert(_("Possible warnings on Report/Clearance!"),"orange")
		return(True)

	def validate_customer_details(self):
		customer_tax_id=frappe.db.get_value("Customer",self.customer,"tax_id")
		if self.customer_address:
			address=frappe.get_doc("Address",self.customer_address)
			return customer_tax_id,address
		else:
			return customer_tax_id,None

	def get_lines(self,tax_category="S"):
		result=""
		f=open(self.item_line,"r")
		temp=f.read()
		item_id=1
		total_before_vat=0
		vat=0
		for i in self.items:
			grand_total=round(i.total_amount,2) or round(i.c_amount,2)
			tax=truncate(round(i.c_amount,2)*round(i.tax_rate,2)/100)
			tax=round(i.tax_amount,2)

			item_name="".join(e for e in i.item_name if (e.isalnum() or e==" "))
			r=replaceAll(temp,{"{item_id}":item_id,"{qty}":num(i.current_qty),"{total}":num(i.c_amount),"{tax_amount}":num(tax),
			"{grand_total}":num(round(i.c_amount+tax,2)),"{discount}":num(0),
			"{item_name}":item_name,"{tax_percentage}":num(i.tax_rate),"{rate}":num(i.c_amount/i.current_qty)
			})
			########################
			# r=replaceAll(temp,{"{item_id}":item_id,"{qty}":num(i.qty),"{total}":num(i.c_amount),"{tax_amount}":num(tax),
			# "{grand_total}":str(round(i.c_amount+tax,2)),"{discount}":num(0),
			# "{item_name}":i.item_name,"{tax_percentage}":num(i.tax_rate),"{rate}":num(i.c_amount)
			# })
			###################
			total_before_vat+=truncate(round(i.c_amount,2))
			vat+=tax
			if i.is_exempt:
				r=r.replace("{tax_category}","E")
			elif i.is_zero_rated:
				r=r.replace("{tax_category}","Z")
			else:
				r=r.replace("{tax_category}","S")
			result+=r
			item_id+=1
		if result[-1]=="\n":
			result=result[:-1]
		return result, total_before_vat,vat
	

	def sign_invoice(self,company,xml,total_after_vat,total_vat):
		#Signing Process - 
		if not xml:
		
			alert("Error : XML file not found","red")
			return False
		#Step 1: Generate Invoice Hash
		#remove extensions, qr and signature
		xml_=xml
		xml_=replaceAll(xml,{"    {ext:UBLExtensions}\n":"","    {QR}\n":"","{cac:signature}":""})
		randname="".join(random.choices('abcdefghijklmnopqrstuvwxyz',k=8))
		hf=open(randname+".xml","w")
		hf.write(xml_)
		hf.close()
		#Canonicalize the Invoice using the C14N11 standard
		cananolized_xml= cananolize(randname+".xml")
		if not cananolized_xml:
			alert("Error while canonicalizing xml invoice.","red")
			return(False)
		hf=open(randname+".xml","w")
		hf.write(cananolized_xml)
		hf.close()
		os.remove(randname+".xml")
		xml_sha256=sha256(cananolized_xml.encode('utf-8')).hexdigest()
		hash_=base64.b64encode(bytes.fromhex(xml_sha256)).decode()         #  <<<<  this is the invoice hash
		self.hash=hash_
		frappe.db.set_value("Clearances",self.name,"hash",hash_)
		pkey=frappe.db.get_value("Company",self.company,"private_key")
		if not pkey or pkey=="":
			alert(_("ZATCA: Private key not found"),"red")
			return(False)
		if "-----BEGIN EC PRIVATE KEY-----" not in pkey:
			pkey="-----BEGIN EC PRIVATE KEY-----\n"+pkey+"\n-----END EC PRIVATE KEY-----"
		f=open(randname+"hash.txt","wb+")
		f.write(base64.b64decode(hash_))
		f.close()
		f=open(randname+"key.pem","wb+")
		f.write(pkey.encode())
		f.close()
		sig=os.popen("openssl dgst -sha256 -sign "+randname+"key.pem "+randname+"hash.txt | base64 /dev/stdin").read()
		signature=str(sig).replace(" ","").replace("\n","")
		os.remove(randname+"key.pem")
		os.remove(randname+"hash.txt")
		#Step 3: Generate Certificate Hash
		try:
			certificate=get_certificate(self.company)
			certificate_sha256=sha256(certificate.encode('utf-8')).hexdigest()
			certificate_hash=base64.b64encode(certificate_sha256.encode("utf-8")).decode("utf-8")
		except:
			alert("ZATCA: Certificate Decode Issue: Error hashing Certificate.","red")
			return(False)
		#Step 4: Populate the Signed Properties Output
		sign_time=str(datetime.now().strftime('%Y-%m-%dT%H:%M:%S'))
		tmp_certificate = "-----BEGIN CERTIFICATE-----\n" + certificate + "\n-----END CERTIFICATE-----"
		try:
			cert = x509.load_pem_x509_certificate(tmp_certificate.encode(), default_backend())
			serial_number=cert.serial_number
			cert_issuer = ''
			for x in range(len(cert.issuer.rdns) - 1, -1, -1):
				cert_issuer += cert.issuer.rdns[x].rfc4514_string() + ", "
			cert_issuer = cert_issuer[:-2]
		except:
			alert("ZATCA: Certificate Decode Issue: Error decoding Certificate.","red")
			return(False)
		#step5:
		signed_properties=""
		serial_number=str(serial_number)
		cet_isser=str(cert_issuer)
		signature_certificate_for_hash ='''<xades:SignedProperties xmlns:xades="http://uri.etsi.org/01903/v1.3.2#" Id="xadesSignedProperties">\n                                    <xades:SignedSignatureProperties>\n                                        <xades:SigningTime>'''+sign_time+'''</xades:SigningTime>\n                                        <xades:SigningCertificate>\n                                            <xades:Cert>\n                                                <xades:CertDigest>\n                                                    <ds:DigestMethod xmlns:ds="http://www.w3.org/2000/09/xmldsig#" Algorithm="http://www.w3.org/2001/04/xmlenc#sha256"/>\n                                                    <ds:DigestValue xmlns:ds="http://www.w3.org/2000/09/xmldsig#">'''+str(certificate_hash) +'''</ds:DigestValue>\n                                                </xades:CertDigest>\n                                                <xades:IssuerSerial>\n                                                    <ds:X509IssuerName xmlns:ds="http://www.w3.org/2000/09/xmldsig#">'''+cert_issuer+'''</ds:X509IssuerName>\n                                                    <ds:X509SerialNumber xmlns:ds="http://www.w3.org/2000/09/xmldsig#">'''+serial_number+'''</ds:X509SerialNumber>\n                                                </xades:IssuerSerial>\n                                            </xades:Cert>\n                                        </xades:SigningCertificate>\n                                    </xades:SignedSignatureProperties>\n                                </xades:SignedProperties>'''
		sha_256_5 = sha256()
		sha_256_5.update(signature_certificate_for_hash.encode())
		signed_properties= base64.b64encode(sha_256_5.hexdigest().encode()).decode('UTF-8')
		replace={"{hash}":hash_,"{signature}":signature,"{certificate}":certificate,"{certificate_hash}":certificate_hash,
		"{signing_time}":sign_time,"{issue_name}":cert_issuer,"{serial_number}":serial_number,
		"{signed_properties}":signed_properties
		}
		extensions=read(self.extensions)
		extensions=replaceAll(extensions,replace)
		qr=read(self.qr_code)
		qr=qr.replace("</cac:Signature>\n","</cac:Signature>")
		tax_id=frappe.db.get_value("Company",self.company,"tax_id")
		#ECDSA signature of the cryptographic stamp tag-9
		public_key,tagnine=company.custom_cet_public_key,company.custom_cert_sig_algo
		if not public_key or not tagnine:
			public_key,tagnine=tag_nine(self.company)
			if not tagnine or not public_key:
				alert("ZATCA: Certificate Decode Issue: Error decoding Certificate.","red")
				return (False)
		try:
			seconds=frappe.utils.get_timedelta(self.posting_time).seconds
		except:
			seconds=self.posting_time.seconds
		h=str(seconds//3600)
		h="0"+h if len(h) ==1 else h
		m=str((seconds%3600)//60)
		m="0"+m if len(m) ==1 else m
		s=str((seconds%3600)%60)
		s="0"+s if len(s) ==1 else s
		issue_time=h+":"+m+":"+s
		timestamp=str(self.posting_date)+"T"+issue_time #+"Z"
		#############################################################   making QR code ##############
		qr_str=qr_code(self.company,tax_id,timestamp,num(total_after_vat),num(total_vat),hash_,signature,public_key,tagnine)
		#qr_str=str(qr_code.base64)
		self.qr_code_text=qr_str
		frappe.db.set_value("Clearances",self.name,"qr_code_text",qr_str)
		qr=qr.replace("{qr_code}",qr_str)
		xml=xml.replace("\n    {ext:UBLExtensions}\n",extensions)
		xml=xml.replace("{QR}\n    ",qr)
		#self.save(ignore_version=True)
		alert(_("Invoice signed successfully"))
		return(xml)

	@frappe.whitelist()
	def clearance(self,show_alert=False):
		company=frappe.get_doc("Company",self.company)
		if company.custom_zatca_status=="Disabled":
			alert(_("ZATCA is disabled"),"red")
			return
		if company.custom_zatca_status=="Compliance Check":
			frappe.msgprint(_("Zatca is running compliance checks, finish onboarding before clearing invoices."))
			return
		if self.simple:
			frappe.throw(_("You can not clear a simple invoice."))
		if not self.xml_path :
			frappe.throw(_("XML file not found, kindly regenerate XML."))
		if not self.hash:
			frappe.throw(_("Hash is not present in the invoice body, kindly regenerate XML."))
		if not self.uuid:
			frappe.throw(_("UUID is not present in the invoice body, kindly regenerate XML."))
		f=open(self.site+self.xml_path,"r")
		xml=f.read()
		f.close()
		encoded=base64.b64encode(xml.encode("utf-8")).decode("utf-8")
		urli=get_urli(company.custom_api_endpoint)
		url=urli+"/invoices/clearance/single"
		Headers = { 'accept' : 'application/json', 'Clearance-Status': '1', 'Accept-Version' : company.accept_version, 'Content-Type': 'application/json', 'Accept-Language': 'en' }
		if company.custom_zatca_status=="Compliance Check":
			auth =company.ccsid_username+":"+company.get_password("ccsid_password")
		else:
			auth =company.pcsid_username+":"+company.get_password("pcsid_password")
		binary_auth = auth.encode('utf-8')
		autorization_binary = base64.b64encode(binary_auth)
		autorization = autorization_binary.decode('utf-8')
		Headers["Authorization"]="Basic "+autorization
		data={"invoiceHash":self.hash,"uuid":self.uuid,"invoice":encoded}
		response = requests.post(url, data=json.dumps(data), headers=Headers)
		status_code=response.status_code
		if status_code==401:
			reporting=_("Reporting Status = ")+"<span style='color:red;'>"+_("NOT_CLEARED")+"</span><br>"
			reporting+=_("Code : 401")+"<br>"
			reporting+=_("Error") +" <b>"+_("Unauthorized")+"</b>"
			if not show_alert:
				frappe.throw(str(reporting))
		rj=response.json()
		############################################################ REJECTED #################################################################
		if status_code!=200 and status_code!=202:
			error=""
			reporting=_("Reporting Status = ")+"<span style='color:red;'>"+_(rj["clearanceStatus"])+"</span><br>"
			reporting=""
			for i in rj["validationResults"]["errorMessages"]:
				reporting+="- "+"<b>"+_(i["code"])+", "+_(i["category"])+"</b> :"
				reporting+=_(str(i["message"]))+"<br>"
				error+="<b style='color:darkred'>"+_(str(i["message"]))+"</b><br>"
			self.custom_zatca_warnings=error
			self.zatca_status="Rejected"
			frappe.db.set_value("Clearances",self.name,"custom_zatca_warnings",error)
			frappe.db.set_value("Clearances",self.name,"zatca_status","Rejected")
			#self.save(ignore_version=True)
			if not show_alert:
				frappe.msgprint(
					title="<span style='color:red;font-weight:700;'>"+_("NOT CLEARED")+"</span>",
					raise_exception=False,
					msg=reporting
				)
			com=_("Fail to clear invoice to ZATCA")+_("Datetime")+": <span style='font-weight:700;'>"+str(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))+"</span><br>"
			com+=error
			comment(self.name,com)
			return False
		else:
			msg=_("Invoice Cleared to zakat tax and customs authority.")+"<br>"
			###################################################### CLEARED with WARNINGS
			if status_code==202:
				warnings=""
				msg+="<span style='font-weight:700;;font-weight:400'>"+_("Warnings")+":</span><br>"
				for i in rj["validationResults"]["warningMessages"]:
					msg+="- "+"<b>"+_(i["code"])+", "+_(i["category"])+"</b> :"
					msg+=_(str(i["message"]))+"<br>"
					warnings+="<b>"+_(str(i["message"]))+"</b><br>"
				self.zatca_status="Cleared with warnings"
				self.custom_zatca_warnings=warnings
				frappe.db.set_value("Clearances",self.name,"custom_zatca_warnings",warnings)
				frappe.db.set_value("Clearances",self.name,"zatca_status","Cleared with warnings")
				com=_("Invoice cleared to ZATCA with warnings.")+_("Datetime")+": <span style='font-weight:700;'>"+str(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))+"</span><br>"
				com+=warnings
				comment(self.name,com)
			######################################################### CLEARED ##################################################
			else:
					
				self.custom_zatca_warnings=""
				frappe.db.set_value("Clearances",self.name,"custom_zatca_warnings","")
				comment(self.name,_("Invoice cleared to ZATCA.")+_("Datetime")+": <span style='font-weight:700;'>"+str(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))+"</span>")
				self.zatca_status="Cleared"
				frappe.db.set_value("Clearances",self.name,"zatca_status","Cleared")
			self.custom_clearing_to_zatka_time=frappe.utils.now()
			frappe.db.set_value("Clearances",self.name,"custom_clearing_to_zatka_time",frappe.utils.now())
			if show_alert:
				alert(_("Invoice Cleared to zakat tax and customs authority."))
			else:
				frappe.msgprint(
					title="<span style='color:green;font-weight:700;'>"+_("CLEARED")+"</span>",
					raise_exception=False,
					msg=msg
			);
			invoice=rj["clearedInvoice"]
			invoice=base64.b64decode(invoice).decode("utf-8")
			f=open(self.site+self.xml_path,"w")
			f.write(invoice)
			f.close()
			qr_code=invoice.split("<cbc:ID>QR</cbc:ID>")[1]
			qr_code=qr_code.split("""mimeCode="text/plain">""")[1]
			qr_code=qr_code.split("<")[0]
			if ">" in qr_code or "<" in qr_code or "\"" in qr_code:
				alert("Error fetching QR Code from Cleared Invoice")
			if self.ksa_einv_qr:
				file_doc=frappe.get_all("File",{"file_url":self.ksa_einv_qr})
				if len(file_doc):
					frappe.delete_doc("File",file_doc[0]["name"])
			qr_image=BytesIO()
			url=qr_create(qr_code,error="L")
			url.png(qr_image,scale=2,quiet_zone=1)
			name=self.xml_path.split("/")[-1].replace("xml","png")
			_file=frappe.get_doc({
				"doctype":"File",
				"file_name":name,
				"is_private":0,
				"content":qr_image.getvalue(),
				"attached_to_doctype":"Clearances",
				"attached_to_name":self.name
			})
			_file.save()
			frappe.db.set_value("Clearances",self.name,"ksa_einv_qr",_file.file_url)
			frappe.db.set_value("Clearances",self.name,"qr_code_text",qr_code)
			self.ksa_einv_qr=_file.file_url
			self.qr_code_text=qr_code
			#self.save(ignore_version=True)
			return(True)
		return (False)


	@frappe.whitelist()
	def compliance(self,show_alert=False):	
		company=frappe.get_doc("Company",self.company)
		if company.custom_zatca_status=="Disabled":
			alert(_("ZATCA is disabled"),"red")
			return
		if not self.xml_path :
			frappe.throw(_("XML file not found, kindly regenerate XML."))
		if not self.hash:
			frappe.throw(_("Hash is not present in the invoice body, kindly regenerate XML."))
		if not self.uuid:
			frappe.throw(_("UUID is not present in the invoice body, kindly regenerate XML."))
		urli=get_urli(company.custom_api_endpoint)
		url=urli+"/compliance/invoices"
		f=open(self.site+self.xml_path,"r")
		xml=f.read()
		f.close()
		encoded=base64.b64encode(xml.encode("utf-8")).decode("utf-8")
		Headers = { 'accept' : 'application/json', 'Accept-Version' : company.accept_version, 'Content-Type': 'application/json', 'Accept-Language': 'en' }
		# a compliance check uses ccsid 
		auth =company.ccsid_username+":"+company.get_password("ccsid_password")
		binary_auth = auth.encode('utf-8')
		autorization_binary = base64.b64encode(binary_auth)
		autorization = autorization_binary.decode('utf-8')
		Headers["Authorization"]="Basic "+autorization
		data={"invoiceHash":self.hash,"uuid":self.uuid,"invoice":encoded}
		response = requests.post(url, data=json.dumps(data), headers=Headers)
		status_code=response.status_code
		if status_code==401:
			reporting=_("Code : 401")+"<br>"
			reporting+=_("Error") +" <b>"+_("Unauthorized")+"</b>"
			if not show_alert:
				frappe.throw(str(reporting))
		rj=response.json()
		head=""
		if len(rj["validationResults"]["infoMessages"])>0:
			head=_("Compliance Check = ")+"<span style='color:green;'>"+rj["validationResults"]["infoMessages"][0]["status"]+"</span>"
		status=""
		
		if rj["validationResults"]["warningMessages"]:
			status+="<span style='color:orange'> "+_("Warning Messages :")+"</span>"+"<br>"
			for w in rj["validationResults"]["warningMessages"]:
				status+=str(w)+"<br>"
		if rj["validationResults"]["errorMessages"]:
			status+="<span style='color:red'> "+_("Error Messages :")+"</span>"+"<br>"
			for w in rj["validationResults"]["errorMessages"]:
				status+=str(w)+"<br>"
		if rj["reportingStatus"]:
			if rj["reportingStatus"]=="REPORTED":
				status+=_("Reporting Status")+" <span style='color:green;font-weight:700;'>"+rj["reportingStatus"]+"</span>"
				status+="<br><b>"+_("This is a compliance check, Invoice is NOT actually reported to Zatca.")+"</b>"
				if not show_alert:
					frappe.msgprint(str(status),head)
				return 1
			else:
				status+=_("Reporting Status")+" <span style='color:red;font-weight:700;'>"+rj["reportingStatus"]+"</span>"
				if not show_alert:
					frappe.msgprint(str(status),head)
				return 0
		if rj["clearanceStatus"]:
			if rj["clearanceStatus"]=="CLEARED":
				status+=_("Clearance Status")+" <span style='color:green;font-weight:700;'>"+rj["clearanceStatus"]+"</span>"
				status+="<br><b>"+_("This is a compliance check, Invoice is NOT actually cleared to Zatca.")+"</b>"
				if not show_alert:
					frappe.msgprint(str(status),head)
				return 1	
			else:
				status+=_("Clearance Status")+" <span style='color:red;font-weight:700;'>"+rj["clearanceStatus"]+"</span>"
				if not show_alert:
					frappe.msgprint(str(status),head)
				return 0
		if not show_alert:
			frappe.msgprint(str(status),head)
#Canonicalize the Invoice using the C14N11 standard,return string
def cananolize(xml_path):
	#try:
		rando="".join(random.choices('abcdefghijklmnopqrstuvwxyz',k=8))
		et = ET.parse(xml_path)
		et.write_c14n(rando+".xml",exclusive=0, with_comments=0)
		f=open(rando+".xml","r")
		cananolized_xml=f.read()
		f.close()
		os.remove(rando+".xml")
		return(cananolized_xml)
	#except:
		#return(None)

def truncate(f):
    return math.floor(f * 100) / 100

def replaceAll(txt,d):
	tmp_txt=txt
	for i in d:
		tmp_txt=tmp_txt.replace(i,str(d[i]))
	return(tmp_txt)

def comment(invoice,msg):
	com=frappe.new_doc("Comment")
	com.comment_type="Comment"
	com.reference_doctype="Clearances"
	com.reference_name=invoice
	com.content=msg
	com.insert()

#hash the xml string using SHA-256 , then encode using HEX-to Base64 Encoder
def get_hash(xml):
	xml_sha256=sha256(xml.encode('utf-8')).hexdigest()
	hash=base64.b64encode(bytes.fromhex(xml_sha256)).decode()
	return hash

def read(file):
	try:
		f=open(file,"r")
		msg=f.read()
		f.close()
		return(msg)
	except:
		return(None)


def tag_nine(company):
	#return public key and signature algorithm of a certificate
	rand="".join(random.choices('abcdefghijklmnopqrstuvwxyz',k=8))   #certificate will stored in a random file in /tmp to avoid certificate collision
	#certificate = x509.load_pem_x509_certificate(cert.encode(), default_backend())
	pcsid=frappe.db.get_value("Company",company,"pcsid_username")
	if not pcsid:
		pcsid=frappe.db.get_value("Company",company,"ccsid_username")
	certificate=base64.b64decode(pcsid.encode("utf-8")).decode()
	if "-----BEGIN CERTIFICATE-----\n" not in certificate:
		certificate = "-----BEGIN CERTIFICATE-----\n" + certificate + "\n-----END CERTIFICATE-----"
	f=open("/tmp/"+rand+".pem","w+")
	f.write(certificate)
	f.close()
	certificate_public_key = "openssl x509 -pubkey -noout -in /tmp/"+rand+".pem"
	#get public key
	zatca_cert_public_key = os.popen(certificate_public_key).read()
	zatca_cert_public_key = zatca_cert_public_key.replace('-----BEGIN PUBLIC KEY-----', '')\
								.replace('-----END PUBLIC KEY-----', '')\
								 .replace('\n', '').replace(' ', '')
	os_cmd="openssl x509 -in /tmp/"+rand+".pem -text -noout"
	cert=os.popen(os_cmd).read()
	cert_find = cert.rfind("Signature Algorithm: ecdsa-with-SHA256")
	#getting signature algorith
	if cert_find > 0 and cert_find + 38 < len(cert):
		cert_sig_algo = cert[cert.rfind("Signature Algorithm: ecdsa-with-SHA256") + 38:].replace('\n', '')\
		.replace(':', '')\
		.replace(' ', '')
		return(zatca_cert_public_key,cert_sig_algo.replace("SignatureValue",""))
	else:
		return(None,None)
def alert(msg,color="green"): 
	frappe.msgprint( _(msg), alert=True, indicator=color)

def num(a):
	return str(round(abs(a),2))

def get_certificate(company):
	pcsid=frappe.db.get_value("Company",company,"pcsid_username")   # <<<< Production csid = certificate 
	if pcsid:
		cert=base64.b64decode(pcsid.encode("utf-8")).decode()
		cert=cert.replace("-----BEGIN CERTIFICATE-----","")
		cert=cert.replace("-----END CERTIFICATE-----","")
		cert=cert.replace("\n","")
		cert=cert.replace("\t","")
		return(cert)
	else:
		ccsid=frappe.db.get_value("Company",company,"ccsid_username")   # <<<< compliance csid = certificate for compliance checks
		if ccsid:
			cert=base64.b64decode(ccsid.encode("utf-8")).decode()
			cert=cert.replace("-----BEGIN CERTIFICATE-----","")
			cert=cert.replace("-----END CERTIFICATE-----","")
			cert=cert.replace("\n","")
			cert=cert.replace("\t","")
		return(cert)
	return(None)

def get_urli(endpoint):
	if endpoint=="Developer Portal" or endpoint=="Developer":
		return("https://gw-fatoora.zatca.gov.sa/e-invoicing/developer-portal")
	elif endpoint=="Simulation":
		return("https://gw-fatoora.zatca.gov.sa/e-invoicing/simulation")
	else:
		return("https://gw-fatoora.zatca.gov.sa/e-invoicing/core")
	

@frappe.whitelist()
def make_return(source_name,target_doc=None):
	clearance=frappe.get_doc("Clearances",source_name)
	r=frappe.copy_doc(clearance)
	r.is_return=1
	r.zatca_status="Pending"
	r.qr_code_text=""
	r.hash=""
	r.signed=0
	r.uuid=""
	r.xml_path
	r.ksa_einv_qr=""
	r.custom_pih=""
	r.custom_clearing_to_zatka_time=""
	r.xml_path=""
	r.custom_zatca_warnings=""
	r.return_against=source_name
	for i in r.items:
		i.current_qty=-1*i.current_qty
		i.current_amount=-1*i.current_amount
	return(r)


