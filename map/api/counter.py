import frappe
import json

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

    results = {}

    for doctype, items in filters_by_doctype.items():
        parent_table = f"`tab{doctype}`"
        print("doctype: ", doctype)
        for item in items:
            name = item.get("name")
            parent_filters = item.get("filters", {})
            child = item.get("child", None)

            if not name: 
                continue

            # ✅ Build Parent WHERE Clause
            parent_conditions = []
            params = {}

            for key, val in parent_filters.items():
                if isinstance(val, list) and val[0] == "!=":
                    parent_conditions.append(f"{parent_table}.`{key}` != %({key})s")
                    params[key] = val[1]
                else:
                    parent_conditions.append(f"{parent_table}.`{key}` = %({key})s")
                    params[key] = val

            parent_where = " AND ".join(parent_conditions) or "1=1"

            # ✅ If no child required → simple count
            if not child:
                sql = f"SELECT COUNT(*) as count FROM {parent_table} WHERE {parent_where}"
                results[name] = frappe.db.sql(sql, params, as_dict=True)[0]["count"]
                continue

            # ✅ Child logic (include / exclude)
            child_table = f"`tab{child['doctype']}`"
            child_filters = child.get("filters", {})
            child_conditions = []

            for key, val in child_filters.items():
                if isinstance(val, list) and val[0] == "!=":
                    child_conditions.append(f"{child_table}.`{key}` != %({key})s")
                    params[key] = val[1]
                else:
                    child_conditions.append(f"{child_table}.`{key}` = %({key})s")
                    params[key] = val

            child_where = " AND ".join(child_conditions) or "1=1"

            # ✅ Include child rows (JOIN)
            if not child.get("exclude", False):
                sql = f"""
                    SELECT COUNT(DISTINCT {parent_table}.name) AS count
                    FROM {parent_table}
                    INNER JOIN {child_table}
                    ON {parent_table}.name = {child_table}.parent
                    WHERE {parent_where} AND {child_where}
                """
            else:
                # ✅ Exclude → parent records with NO matching child
                sql = f"""
                    SELECT COUNT(*) as count
                    FROM {parent_table}
                    WHERE {parent_where}
                    AND {parent_table}.name NOT IN (
                        SELECT DISTINCT parent FROM {child_table} WHERE {child_where}
                    )
                """

            results[name] = frappe.db.sql(sql, params, as_dict=True)[0]["count"]

    return results
