import frappe
import base64
import os
from typing import List
import json
from frappe import _
from frappe.utils import getdate
from collections import defaultdict
import calendar
from datetime import date

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
            "lodge_name": r.get("lodge_name"),
            "lodge_no": r.get("lodge_no"),
            "lodge_type": r.get("lodge_type"),
            "lodge_date": r.get("lodge_date"),
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

@frappe.whitelist()
def get_lodge_members(lodge_no):
    rows = frappe.db.sql(
        """
        SELECT DISTINCT
            m.name,
            m.full_name,
            m.id_number,
            m.member_key,
            m.overall_status,
            ol.lodge_type,
            ol.status AS lodge_status
        FROM `tabMembers` m
        LEFT JOIN `tabLodges` ol
            ON ol.parent = m.name
            AND ol.lodge_no = %(lodge_no)s
            # AND ol.status = 'Active'
        WHERE
            # m.overall_status = 'Active'
            # AND (
            m.lodge = %(lodge_no)s
            OR ol.parent IS NOT NULL
            # )
        """,
        {"lodge_no": lodge_no},
        as_dict=True,
    )

    members = {}
    honorary_members = {}
    restore_members = {}

    excluded_restore_statuses = {
        "active",
        "dropped from the roll",
        "deceased",
    }

    for row in rows:
        name = row["name"]
        lodge_type = (row.get("lodge_type") or "").lower()
        status = (row.get("overall_status") or "").strip().lower()
        lodge_status = (row.get("lodge_status") or "").strip().lower()

        member_data = {
            "name": name,
            "full_name": row["full_name"],
            "id_number": row.get("id_number") or "",
            "member_key": row.get("member_key"),
            "overall_status": row.get("overall_status"),
        }

        # Normal active members
        if lodge_status == "active" or status == "active":
            if lodge_status == "active" and lodge_type == "honorary":
                honorary_members[name] = member_data
            else:
                members[name] = member_data
        elif status not in excluded_restore_statuses:
            restore_members[name] = member_data

    return {
        "members": list(members.values()),
        "honoraryMembers": list(honorary_members.values()),
        "restoreMembers": list(restore_members.values()),
    }

    
ACTION_NO_ACTION = "No Action"
ACTION_FOR_SUSPENSION = "For Suspension"
ACTION_SUSPENDED = "Suspended for Non-attendance"
ACTION_RESTORED = "Restored"


def _get_lodge_roster(lodge_no):
    """
    Returns the full working roster for a lodge: home members plus
    dual/affiliated members from other lodges. Honorary members are
    returned separately since they aren't subject to attendance/suspension.
    """
    rows = frappe.db.sql(
        """
        SELECT DISTINCT
            m.name,
            m.full_name,
            m.id_number,
            m.member_key,
            m.overall_status,
            ol.lodge_type,
            ol.status AS lodge_status
        FROM `tabMembers` m
        LEFT JOIN `tabLodges` ol
            ON ol.parent = m.name
            AND ol.lodge_no = %(lodge_no)s
            # AND ol.status = 'Active'
        WHERE
            # m.overall_status = 'Active'
            # AND (
            m.lodge = %(lodge_no)s
            OR ol.parent IS NOT NULL
            # )
        """,
        {"lodge_no": lodge_no},
        as_dict=True,
    )

    roster = {}
    honorary = {}


    for row in rows:
        lodge_type = (row.get("lodge_type") or "").lower()
        status = (row.get("overall_status") or "").strip().lower()
        lodge_status = (row.get("lodge_status") or "").strip().lower()

        # Normal active members
        if lodge_status == "active" or status == "active":
            if lodge_status == "active" and lodge_type == "honorary":
                honorary[row["name"]] = row
            else:
                roster[row["name"]] = row


    return list(roster.values()), list(honorary.values())


@frappe.whitelist()
def get_lodge_attendance_roster(lodge_no):
    members, honorary_members = _get_lodge_roster(lodge_no)
    return {
        "members": [
            {
                "name": m["name"],
                "full_name": m["full_name"],
                "id_number": m["id_number"],
                "member_key": m["member_key"],
            }
            for m in members
        ],
        "honoraryMembers": [
            {"name": m["name"], "full_name": m["full_name"]}
            for m in honorary_members
        ],
    }


@frappe.whitelist()
def submit_minutes_attendance(lodge_no, meeting_title, meeting_date, present_members=None):
    """
    Marks every working member of a lodge (home + dual/affiliated)
    Present/Absent for a given meeting, and flags members for suspension
    after 3 consecutive absences at that same lodge.
    """
    if isinstance(present_members, str):
        present_members = frappe.parse_json(present_members)

    present_members = set(present_members or [])

    if not lodge_no:
        frappe.throw(_("Lodge number is required"))

    roster, _honorary = _get_lodge_roster(lodge_no)
    lodge_members = [row["name"] for row in roster]

    flagged_for_suspension = []
    restored = []

    for member_name in lodge_members:
        member_doc = frappe.get_doc("Members", member_name)
        attendance = "Present" if member_name in present_members else "Absent"

        # this member's history at THIS lodge specifically
        lodge_history = [
            row for row in (member_doc.meeting_and_attendance or [])
            if row.lodge_no == lodge_no
        ]
        lodge_history.sort(key=lambda r: getdate(r.meeting_date), reverse=True)

        most_recent_action = lodge_history[0].action if lodge_history else ACTION_NO_ACTION
        action = ACTION_NO_ACTION

        if attendance == "Absent":
            last_two = lodge_history[:2]
            if len(last_two) == 2 and all(r.attendance == "Absent" for r in last_two):
                action = ACTION_FOR_SUSPENSION
                flagged_for_suspension.append(member_name)
        else:
            # attended — clear a prior flag/suspension
            if most_recent_action in (ACTION_FOR_SUSPENSION, ACTION_SUSPENDED):
                action = ACTION_RESTORED
                restored.append(member_name)

        member_doc.append("meeting_and_attendance", {
            "meeting_title": meeting_title,
            "meeting_date": meeting_date,
            "lodge_no": lodge_no,
            "attendance": attendance,
            "action": action,
        })

        member_doc.save(ignore_permissions=True)

    return {
        "message": "Attendance recorded",
        "total_members": len(lodge_members),
        "present_count": len(present_members),
        "absent_count": len(lodge_members) - len(present_members),
        "flagged_for_suspension": flagged_for_suspension,
        "restored": restored,
    }


@frappe.whitelist()
def get_lodge_attendance_report(lodge_no, year, from_month, to_month):
    # ---------------------------------------
    # Set dates to fetch
    # ---------------------------------------
    year = int(year)
    from_month = int(from_month)
    to_month = int(to_month)

    from_date = date(year, from_month, 1)

    last_day = calendar.monthrange(year, to_month)[1]
    to_date = date(year, to_month, last_day)

    # ---------------------------------------
    # Get all eligible lodge members
    # ---------------------------------------
    members = frappe.db.sql(
        """
        SELECT DISTINCT
            m.name,
            m.full_name,
            m.member_key,
            m.id_number,
            m.overall_status,

            CASE
                WHEN ol.lodge_type IS NULL THEN 'Regular'
                ELSE ol.lodge_type
            END AS membership_type

        FROM `tabMembers` m

        LEFT JOIN `tabLodges` ol
            ON ol.parent = m.name
            AND ol.lodge_no = %(lodge_no)s

        WHERE
            (
                m.overall_status = 'ACTIVE'
                AND m.lodge = %(lodge_no)s
            )
            OR
            (
                ol.lodge_no = %(lodge_no)s
                AND ol.status = 'Active'
                AND ol.lodge_type IN (
                    'DUAL',
                    'HONORARY',
                    'AFFILIATED',
                    'CHARTER'
                )
            )

        ORDER BY m.full_name
        """,
        {"lodge_no": lodge_no},
        as_dict=True,
    )

    member_names = [m["name"] for m in members]

    attendance_rows = frappe.get_all(
        "Meeting and Attendance",
        filters={
            "parent": ["in", member_names],
            "meeting_date": ["between", [from_date, to_date]],
            "lodge_no": lodge_no
        },
        fields=[
            "parent",
            "meeting_date",
            "attendance",
            "action",
        ],
        order_by="meeting_date asc",
    )

    attendance_by_member = {}

    for row in attendance_rows:
        attendance_by_member.setdefault(row.parent, []).append(row)

    return {
        "from_date": str(from_date),
        "to_date": str(to_date),
        "members": [
            {
                **member,
                "attendance": attendance_by_member.get(member["name"], [])
            }
            for member in members
        ]
    }