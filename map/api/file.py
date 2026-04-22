import frappe
from typing import Optional

@frappe.whitelist()
def delete_file_by_filters(
    file_url: str,
    attached_to_name: str,
    attached_to_field: Optional[str] = None,
    doctype: Optional[str] = None,
    ignore_permissions: bool = False
) -> int:
    """
    Delete File records based on file_url, attached_to_name, and attached_to_field.

    Args:
        file_url (str): File URL (/files/xxx or /private/files/xxx)
        attached_to_name (str): Document name
        attached_to_field (str, optional): Field name where file is attached
        doctype (str, optional): DocType
        ignore_permissions (bool): Skip permission checks

    Returns:
        int: Number of deleted files
    """

    filters = {
        "file_url": file_url,
        "attached_to_name": attached_to_name,
    }

    if attached_to_field:
        filters["attached_to_field"] = attached_to_field

    if doctype:
        filters["attached_to_doctype"] = doctype

    # Step 1: Find matching File records
    file_names = frappe.get_all(
        "File",
        filters=filters,
        pluck="name"
    )

    # Step 2: Delete files
    for name in file_names:
        frappe.delete_doc("File", name, ignore_permissions=ignore_permissions)

    # Step 3: Clear field in the document
    if attached_to_field:
        frappe.db.set_value(
            doctype,
            attached_to_name,
            attached_to_field,
            None
        )

    return len(file_names)