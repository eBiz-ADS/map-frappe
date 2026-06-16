import frappe


@frappe.whitelist()
def get_select_values(doctype: str):
    meta = frappe.get_meta(doctype)

    # ✅ correct way to get repeated query params
    fieldnames = frappe.request.args.getlist("fieldname")

    result = {}

    for fname in fieldnames:
        field = meta.get_field(fname)

        if not field:
            frappe.throw(f"Field '{fname}' not found")

        if field.fieldtype != "Select":
            frappe.throw(f"Field '{fname}' is not Select")

        result[fname] = [
            v.strip()
            for v in (field.options or "").split("\n")
            if v.strip()
        ]

    return result