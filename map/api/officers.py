import frappe
from frappe.utils import now

@frappe.whitelist()
def bulk_update_status(docnames: list[str], status: str, remarks: str | None = None,):
    # 1️⃣ Input validation
    if not isinstance(docnames, list) or not docnames:
        frappe.throw("Invalid or empty document list")

    if not isinstance(status, str) or not status.strip():
        frappe.throw("Invalid status value")

    # 2️⃣ Permission check (important)
    frappe.has_permission("Officers", "write", throw=True)

    # 3️⃣ Optional: enforce allowed statuses
    allowed_statuses = {"Posted","Unposted","Received", "Pending", "Created", "Returned", "Resubmitted"}
    if status not in allowed_statuses:
        frappe.throw(f"Status '{status}' is not allowed")

    # 4️⃣ Ensure all docnames exist (prevents silent partial updates)
    existing = frappe.db.sql_list(
        """
        SELECT name
        FROM `tabOfficers`
        WHERE name IN %s
        """,
        (tuple(docnames),),
    )

    if not existing:
        frappe.throw("No matching documents found")

    # 5️⃣ Bulk update (safe parameterized SQL)
    frappe.db.sql(
        """
        UPDATE `tabOfficers`
        SET
            status = %s,
            remarks = %s,
            modified = %s
        WHERE name IN %s
        """,
        (status, remarks if status == "Returned" else None, now(), tuple(existing)),
    )
    
    frappe.logger().info(
        f"[bulk_update_status] Updated {len(existing)} records to '{status}': {existing}"
    )

    frappe.db.commit()

    return {
        "updated": len(existing),
        "status": status
    }
