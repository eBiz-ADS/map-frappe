import frappe, json

@frappe.whitelist()
def count_records(filters_by_doctype=None):
  
    """
    Count records per Doctype with custom names.

    Example payload:
    {
      "Members": [
        {"name": "total_petitioner", "filters": {"overall_status": "PETITIONER"}},
        {"name": "total_apprentice", "filters": {"overall_status": "APPRENTICE"}}
      ],
      "Sales Invoice": [
        {"name": "paid_invoices", "filters": {"status": "Paid"}}
      ]
    }
    """
    filters_by_doctype = json.loads(filters_by_doctype) if filters_by_doctype else {}
    if not filters_by_doctype:
        return {"error": "No filters provided"}

    results = {}

    for doctype, filter_items in filters_by_doctype.items():
        for item in filter_items:
            name = item.get("name")
            filters = item.get("filters", {})

            if not name:
                continue  # Skip unnamed entries

            try:
                count = frappe.db.count(doctype, filters=filters)
                results[name] = count
            except Exception as e:
                results[name] = f"Error: {str(e)}"

    return results
