# Copyright (c) 2025, eBiZolution and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Events(Document):
	pass

def on_update(doc, method=None):
	current_attendees = {attendee.member for attendee in doc.attendees if attendee.member}
	#frappe.msgprint(f"Doc {current_attendees}")
	# For each attendee in Event, update their Member record
	for attendee in doc.attendees:
		if not attendee.member:
			continue

		member = frappe.get_doc("Members", attendee.member)  # assuming attendee has a field 'member'

		events = member.member_event or []

		existing_row = next((ev for ev in events if ev.event == doc.name), None)
		#frappe.msgprint(f"Doc {attendee.status}")
		if existing_row:
			#existing_row.event_date = doc.date_time
			existing_row.status = attendee.status
			existing_row.proof_of_payment = attendee.proof_of_payment
			existing_row.reference_id = attendee.reference_id
			#existing_row.event_name = doc.event_name

		else:
			row = member.append("member_event", {})
			row.event = doc.name
			#row.event_name = doc.event_name
			#row.event_date = doc.date_time
			row.status = attendee.status
			row.proof_of_payment = attendee.proof_of_payment
			row.reference_id = attendee.reference_id

		member.save(ignore_permissions=True)

	linked_members = frappe.get_all(
		"Member Event",
		filters={"event": doc.name},
		fields=["parent"]
	)

	for m in linked_members:
		if m.parent not in current_attendees:
			member = frappe.get_doc("Members", m.parent)
			#frappe.msgprint(f"Doc {member.member_event[0].event}")
			if not member.member_event:
				member.member_event = []
			for ev in member.member_event[:]:
				if ev.event == doc.name:
					member.remove(ev)

			member.save(ignore_permissions=True)
