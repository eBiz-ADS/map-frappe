import frappe
import base64
import os
from typing import List
import json

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


@frappe.whitelist()
def add_new_masonic_records(member, records):
    if isinstance(records, str):
        records = frappe.parse_json(records)

    if not records:
        frappe.throw(_("No records provided"))

    member_doc = frappe.get_doc("Members", member)

    allowed_types = ["Affiliation", "Awards", "Change In Status", "Change In Member Profile", "Officer"]

    for r in records:
        # skip empty rows
        if not r.get("record_type"):
            continue

        if r.get("record_type") not in allowed_types:
            frappe.throw(_("Invalid record type: {0}").format(r.get("record_type")))

        member_doc.append("masonic_service_records", {
            "record_type": r.get("record_type"),
            "record_value": r.get("record_value"),
            "additional_info": r.get("additional_info"),
            "lodge_no": r.get("lodge_no"),
            "lodge_name": r.get("lodge_name"),
            "date_encoded": r.get("date_encoded"),
            "date_official": r.get("date_official"),
			"record_encoder": r.get("record_encoder")
        })

    member_doc.save(ignore_permissions=True)

    return {
        "message": "Records added successfully",
        "count": len(records)
    }

    
@frappe.whitelist()
def add_other_lodges(member, records):
    if isinstance(records, str):
        records = frappe.parse_json(records)

    if not records:
        frappe.throw(_("No records provided"))

    member_doc = frappe.get_doc("Members", member)

    # allowed_types = ["Affiliation", "Awards", "Change In Status", "Change In Member Profile", "Officer"]

    for r in records:
        # skip empty rows
        if not r.get("lodge_no"):
            continue

        # if r.get("record_type") not in allowed_types:
        #     frappe.throw(_("Invalid record type: {0}").format(r.get("record_type")))

        member_doc.append("other_lodges", {
            "lodge_no": r.get("lodge_no"),
            "lodge_date": r.get("lodge_date"),
            "lodge_type": r.get("lodge_type"),
            "lodge_name": r.get("lodge_name"),
            "status": r.get("status"),
        })

    member_doc.save(ignore_permissions=True)

    return {
        "message": "Records added successfully",
        "count": len(records)
    }

@frappe.whitelist()
def add_new_masonic_records_petitioner(petitioner, records):
    if isinstance(records, str):
        records = frappe.parse_json(records)

    if not records:
        frappe.throw(_("No records provided"))

    member_doc = frappe.get_doc("Petitioners List", petitioner)

    allowed_types = ["Affiliation", "Awards", "Change In Status", "Change In Member Profile", "Officer"]

    for r in records:
        # skip empty rows
        if not r.get("record_type"):
            continue

        if r.get("record_type") not in allowed_types:
            frappe.throw(_("Invalid record type: {0}").format(r.get("record_type")))

        member_doc.append("masonic_service_records", {
            "record_type": r.get("record_type"),
            "record_value": r.get("record_value"),
            "additional_info": r.get("additional_info"),
            "lodge_no": r.get("lodge_no"),
            "lodge_name": r.get("lodge_name"),
            "date_encoded": r.get("date_encoded"),
            "date_official": r.get("date_official"),
			"record_encoder": r.get("record_encoder")
        })

    member_doc.save(ignore_permissions=True)

    return {
        "message": "Records added successfully",
        "count": len(records)
    }


@frappe.whitelist()
def update_masonic_record(member, record_id, updates):
    member_doc = frappe.get_doc("Members", member)

    for row in member_doc.masonic_records:
        if row.name == record_id:
            for k, v in updates.items():
                setattr(row, k, v)
            break

    member_doc.save(ignore_permissions=True)
    return {"message": "updated"}


@frappe.whitelist()
def update_change_request_field_status(rows, status):
    if isinstance(rows, str):
        rows = frappe.parse_json(rows)

    for row_name in rows:
        frappe.db.set_value(
            "Change Request Fields",
            row_name,
            "status",
            status,
            update_modified=False
        )

    frappe.db.commit()

    return {
        "message": "Statuses updated",
        "count": len(rows)
    }