# Copyright (c) 2025, eBiZolution and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class Petitioners(Document):
	def validate(self):
		self.set_full_name()

	def set_full_name(self):
		middle_intitial = self.middle_name[0] + "." if self.middle_name else ""
		self.full_name = " ".join(filter(None, [self.first_name, middle_intitial, self.last_name]))