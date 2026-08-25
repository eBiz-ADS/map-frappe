# Copyright (c) 2025, eBiZolution and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class Members(Document):
	def validate(self):
		self.set_full_name()

	def set_full_name(self):
		if not self.full_name:
			self.full_name = " ".join(
				filter(None, [
					self.first_name,
					# self.middle_name,
					self.last_name,
				])
			)