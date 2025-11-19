# Copyright (c) 2025, eBiZolution and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ConferralReport(Document):
	def before_insert(self):
		self.flags.petitioner_data = frappe.form_dict.get("petitioner_data")

	def on_update(self):
		petitioners_data = self.flags.petitioner_data or []
		frappe.logger().info("Petitioners Data: {}".format(petitioners_data))

		# Iterate
		for petitioner in petitioners_data:
			member_doc = frappe.get_doc({
				"doctype": "Petitioners Conferral",
				"petitioner": petitioner.get("petitioner"),
			}).insert(ignore_permissions=True)

			# Create Conferral Team
			for item in petitioner.get("conferral_team", []):
				frappe.get_doc({
					"doctype": "Conferral Team",
					"member": item.get("member"),
					"parent": member_doc.name,
					"parentfield": "conferral_team",
					"parenttype": "Petitioners Conferral"
				}).insert(ignore_permissions=True)

			frappe.get_doc({
					"doctype": "Petitioners Conferral Table",
					"petitioners_conferral": member_doc.name,
					"parent": self.name,
					"parentfield": "petitioners",
					"parenttype": "Conferral Report"
				}).insert(ignore_permissions=True)
					
		# self.save(ignore_permissions=True)


			


	
	