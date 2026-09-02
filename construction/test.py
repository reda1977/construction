# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

# IMPORTANT: only import safe functions as this module will be included in jinja environment
import frappe
from dateutil.parser._parser import ParserError
import subprocess
import operator
import re, datetime, math, time
import babel.dates
from babel.core import UnknownLocaleError
from dateutil import parser
from num2words import num2words
from six.moves import html_parser as HTMLParser
from six.moves.urllib.parse import quote, urljoin
from html2text import html2text
from markdown2 import markdown, MarkdownError
from six import iteritems, text_type, string_types, integer_types

DATE_FORMAT = "%Y-%m-%d"
TIME_FORMAT = "%H:%M:%S.%f"
DATETIME_FORMAT = DATE_FORMAT + " " + TIME_FORMAT
@frappe.whitelist()
def get_period_details():
    return "hello world"
@frappe.whitelist()
def test(doctype,doc_name=""):
        import pyqrcode
        import io
        import base64
        from cryptography.fernet import Fernet
        key = b"evGs8445XIFtoWj8NUi7A-IxiGb7_mNRejkMXS9wmG0="
        fernet = Fernet(key)
        encMessage = fernet.encrypt(doc_name.encode())
        return ("https://business.advanced-elements.deom.com.sa/api/method/frappe.utils.print_format.call_download_pdf?doctype={0}&name={1}".format(doctype,encMessage.decode()))





