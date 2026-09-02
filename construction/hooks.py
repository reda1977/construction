from . import __version__ as app_version

app_name = "construction"
app_title = "Construction"
app_publisher = "ERP Cloud Systems"
app_description = "Custom App For Clearances"
app_icon = "octicon octicon-file-directory"
app_color = "grey"
app_email = "mg@erpcloud.systems"
app_license = "MIT"

# Includes in <head>
# ------------------

# NOTE: Frappe reads custom Jinja methods/filters from the "jinja" hook
# (see frappe.utils.jinja.get_jinja_hooks()), not "jenv" -- the old key
# name was silently ignored, so getqrcode() was never registered in the
# Jinja/PDF rendering environment and print formats calling
# getqrcode(doc.doctype, doc) failed with "'getqrcode' is undefined".
#
# Also: get_jinja_hooks() -> get_obj_dict_from_paths() takes plain dotted
# import paths and registers each callable under its own __name__ -- it
# does NOT understand the "alias:dotted.path" colon syntax. Passing
# "testbaaa:construction.test.test" makes Frappe try to import a module
# literally named "testbaaa:construction.test.test", which fails and
# raises AppNotInstalledError -- crashing every single page on the site
# (this is what took the whole site down after the jenv->jinja rename).
# The fix is to list plain "app.module.function" paths; the function is
# then exposed in Jinja under its real name (construction.fatoora.getqrcode
# is still called as getqrcode(...) in print formats since that's its
# actual function name).
#
# construction.test.test itself is also removed here: resolving it forces
# a full import of construction/test.py, which pulls in a long chain of
# third-party packages (dateutil, babel, num2words, six, html2text,
# markdown2, ...) at module load time. None of those are declared in
# requirements.txt, and on this server html2text is not installed, so
# importing that module crashed every page again even after the
# jenv->jinja / colon-syntax fix. Nothing in this app actually calls
# testbaaa(...)/test(...) from a template, so it's dropped rather than
# fixing its whole dependency chain under production pressure.
jinja = {
	"methods": [
		"construction.fatoora.getqrcode",
		#"today_hijri:frappe.utils.today_hijri","to_hijri:frappe.utils.to_hijri"
	]
}




doc_events = {
"Journal Entry": {
	"on_submit": "construction.construction.overrides.journal_entry.journal_entry.update_clearance_on_submit",
	"on_cancel": "construction.construction.overrides.journal_entry.journal_entry.update_clearance_on_cancel",
	"on_cancel": "construction.construction.overrides.journal_entry.journal_entry.cancel_clearance_on_je_cancel",
}
}

# include js, css files in header of desk.html
# app_include_css = "/assets/construction/css/construction.css"
# app_include_js = "/assets/construction/js/construction.js"

# include js, css files in header of web template
# web_include_css = "/assets/construction/css/construction.css"
# web_include_js = "/assets/construction/js/construction.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "construction/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Installation
# ------------

# before_install = "construction.install.before_install"
# after_install = "construction.install.after_install"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "construction.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
#	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"construction.tasks.all"
# 	],
# 	"daily": [
# 		"construction.tasks.daily"
# 	],
# 	"hourly": [
# 		"construction.tasks.hourly"
# 	],
# 	"weekly": [
# 		"construction.tasks.weekly"
# 	]
# 	"monthly": [
# 		"construction.tasks.monthly"
# 	]
# }

# Testing
# -------

# before_tests = "construction.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "construction.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "construction.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]


# User Data Protection
# --------------------

user_data_fields = [
	{
		"doctype": "{doctype_1}",
		"filter_by": "{filter_by}",
		"redact_fields": ["{field_1}", "{field_2}"],
		"partial": 1,
	},
	{
		"doctype": "{doctype_2}",
		"filter_by": "{filter_by}",
		"partial": 1,
	},
	{
		"doctype": "{doctype_3}",
		"strict": False,
	},
	{
		"doctype": "{doctype_4}"
	}
]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"construction.auth.validate"
# ]

