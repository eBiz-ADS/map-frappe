import frappe
from frappe import rename_doc

@frappe.whitelist()
def update_district(name, data):
    data = frappe.parse_json(data)

    doc = frappe.get_doc("District", name)

    old_name = doc.name

    # Update fields
    doc.update(data)
    doc.save()

    # Rename if district_id_code changed
    if data.get("district") and data["district"] != old_name:

        rename_doc(
            "District",
            old_name,
            data["district"],
            force=True
        )

        doc = frappe.get_doc("District", data["district"])

    return doc