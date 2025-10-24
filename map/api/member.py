import frappe
import base64
import os

@frappe.whitelist()
def get_member_files_events(member_id):
	member = frappe.get_doc("Members", member_id)
	files = frappe.get_all(
		"Uploaded Documents",
		filters={"reference_doctype": "Members", "reference_name": member_id},
		fields=["document_name", "document","name"]
	)
	#return files
	file_data_list = []
	for f in files:
		if not f.document:
			continue
		file_name = frappe.get_value("File", {"name": f.document}, "name")
		if not file_name:
			file_name = frappe.get_value("File", {"file_url": f.document}, "name")
		if not file_name:
			continue

		content = None
		file_doc = frappe.get_doc("File", file_name)

		for folder in ["public", "private"]:
			file_path = frappe.get_site_path(folder,"files", os.path.basename(file_doc.file_url.lstrip("/")))
			if os.path.exists(file_path):
				with open(file_path, "rb") as fp:
					content = base64.b64encode(fp.read()).decode("utf-8")
				break

		file_data_list.append({
			"file_name": file_doc.file_name,
			"file_url": file_doc.file_url,
			"is_private": file_doc.is_private,
			"download_url": f"/api/method/frappe.utils.file_manager.download_file?file_url={file_doc.file_url}",
			"content": content
		})
	events = frappe.db.sql("""
		SELECT e.name, e.event_name, e.date_time, e.status
		FROM `tabEvents` e
		INNER JOIN `tabAttendees` em ON em.parent = e.name
		WHERE em.member = %s
	""", (member_id,), as_dict=True)
	
	return{
		"member": member,
		"files": file_data_list,
		"events": events
	}

@frappe.whitelist()
def get_member_events(member_id): 
	member = frappe.get_doc("Members", member_id)
	checker = frappe.db.get_all("Attendees")
	events = frappe.db.sql("""
		SELECT e.name, e.event_name, e.date_time
		FROM `tabEvents` e
		INNER JOIN `tabAttendees` em ON em.parent = e.name
		WHERE em.member = %s
	""", (member_id,), as_dict=True)

	return { "member": member, "events": events}

