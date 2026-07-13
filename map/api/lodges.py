import frappe
from frappe import rename_doc

@frappe.whitelist()
def update_lodge(name, data):
    data = frappe.parse_json(data)

    doc = frappe.get_doc("Lodge List", name)

    old_name = doc.name

    # Update fields
    doc.update(data)
    doc.save()

    # Rename if district_id_code changed
    if data.get("lodge_no") and data["lodge_no"] != old_name:

        rename_doc(
            "Lodge List",
            old_name,
            str(data["lodge_no"]),
            force=True
        )

        doc = frappe.get_doc("Lodge List", data["lodge_no"])

    return doc