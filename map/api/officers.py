import frappe
from frappe.utils import now

@frappe.whitelist()
def bulk_update_status(
    docnames: list[str],
    status: str,
    remarks: str | None = None,
):
    # 1. Input validation
    if not isinstance(docnames, list) or not docnames:
        frappe.throw("Invalid or empty document list")

    if not isinstance(status, str) or not status.strip():
        frappe.throw("Invalid status value")

    # 2. Permission check
    frappe.has_permission("Officers", "write", throw=True)

    # 3. Validate status
    allowed_statuses = {
        "Posted", "Unposted", "Received", "Pending",
        "Created", "Returned", "Resubmitted",
    }

    if status not in allowed_statuses:
        frappe.throw(f"Status '{status}' is not allowed")

    # 4. Fetch existing officers and their member keys
    existing = frappe.db.sql(
        """
        SELECT
            o.name AS officer_name,
            o.position,
            m.name AS member_name
        FROM `tabOfficers` o
        LEFT JOIN `tabMembers` m
            ON m.name = o.member
        WHERE o.name IN %s
        """,
        (tuple(docnames),),
        as_dict=True,
    )

    if not existing:
        frappe.throw("No matching documents found")

    existing_names = [row.officer_name for row in existing]
    member_keys = list({
        row.member_name
        for row in existing
        if row.member_name
    })

    # 5. Update status
    frappe.db.sql(
        """
        UPDATE `tabOfficers`
        SET
            status = %s,
            remarks = %s,
            modified = %s
        WHERE name IN %s
        """,
        (
            status,
            remarks if status == "Returned" else None,
            now(),
            tuple(existing_names),
        ),
    )

    frappe.db.commit()

    frappe.logger().info(
        f"[bulk_update_status] Updated {len(existing_names)} records "
        f"to '{status}': {existing_names}"
    )

    return {
        "updated": len(existing_names),
        "docnames": existing_names,
        "officers": existing,
        "member_keys": member_keys,
        "status": status,
    }