import frappe
import json
from datetime import date
import calendar

@frappe.whitelist()
def count_records(filters_by_doctype=None):

    filters_by_doctype = json.loads(filters_by_doctype) if filters_by_doctype else {}
    results = {}

    for doctype, items in filters_by_doctype.items():

        parent_table = f"`tab{doctype}`"

        for item in items:

            name = item.get("name")
            if not name:
                continue

            parent_filters = item.get("filters", {})
            child = item.get("child", None)

            parent_conditions = []
            params = {}

            # =========================
            # PARENT FILTERS
            # =========================
            for key, val in parent_filters.items():

                # BETWEEN
                if isinstance(val, list) and val[0] == "between":
                    parent_conditions.append(
                        f"{parent_table}.`{key}` BETWEEN %({key}_start)s AND %({key}_end)s"
                    )
                    params[f"{key}_start"] = val[1][0]
                    params[f"{key}_end"] = val[1][1]

                # IN
                elif isinstance(val, list) and val[0] == "IN":
                    placeholders = ", ".join([f"%({key}_{i})s" for i in range(len(val[1]))])
                    parent_conditions.append(
                        f"{parent_table}.`{key}` IN ({placeholders})"
                    )
                    for i, v in enumerate(val[1]):
                        params[f"{key}_{i}"] = v

                # NOT EQUAL
                elif isinstance(val, list) and val[0] == "!=":
                    parent_conditions.append(
                        f"{parent_table}.`{key}` != %({key})s"
                    )
                    params[key] = val[1]

                elif isinstance(val, list) and val[0] == ">":
                    parent_conditions.append(
                        f"CAST({parent_table}.`{key}` AS UNSIGNED) > %({key})s"
                    )
                    params[key] = val[1]
                    
                # EQUAL (default)
                else:
                    parent_conditions.append(
                        f"{parent_table}.`{key}` = %({key})s"
                    )
                    params[key] = val

            parent_where = " AND ".join(parent_conditions) or "1=1"

            # =========================
            # NO CHILD → SIMPLE COUNT
            # =========================
            if not child:
                sql = f"""
                    SELECT COUNT(*) AS count
                    FROM {parent_table}
                    WHERE {parent_where}
                """
                results[name] = frappe.db.sql(sql, params, as_dict=True)[0]["count"]
                continue

            # =========================
            # CHILD FILTERS
            # =========================
            child_table = f"`tab{child['doctype']}`"
            child_filters = child.get("filters", {})

            child_conditions = []

            for key, val in child_filters.items():

                if isinstance(val, list) and val[0] == "between":
                    child_conditions.append(
                        f"{child_table}.`{key}` BETWEEN %({key}_start)s AND %({key}_end)s"
                    )
                    params[f"{key}_start"] = val[1][0]
                    params[f"{key}_end"] = val[1][1]

                elif isinstance(val, list) and val[0] == "IN":
                    placeholders = ", ".join([f"%({key}_{i})s" for i in range(len(val[1]))])
                    child_conditions.append(
                        f"{child_table}.`{key}` IN ({placeholders})"
                    )
                    for i, v in enumerate(val[1]):
                        params[f"{key}_{i}"] = v

                elif isinstance(val, list) and val[0] == "!=":
                    child_conditions.append(
                        f"{child_table}.`{key}` != %({key})s"
                    )
                    params[key] = val[1]

                else:
                    child_conditions.append(
                        f"{child_table}.`{key}` = %({key})s"
                    )
                    params[key] = val

            child_where = " AND ".join(child_conditions) or "1=1"

            # =========================
            # JOIN OR EXCLUDE CHILD
            # =========================
            if not child.get("exclude", False):

                sql = f"""
                    SELECT COUNT(DISTINCT {parent_table}.name) AS count
                    FROM {parent_table}
                    INNER JOIN {child_table}
                        ON {parent_table}.name = {child_table}.parent
                    WHERE {parent_where} AND {child_where}
                """

            else:

                sql = f"""
                    SELECT COUNT(*) AS count
                    FROM {parent_table}
                    WHERE {parent_where}
                    AND {parent_table}.name NOT IN (
                        SELECT DISTINCT parent
                        FROM {child_table}
                        WHERE {child_where}
                    )
                """

            results[name] = frappe.db.sql(sql, params, as_dict=True)[0]["count"]

    return results


@frappe.whitelist()
def get_report_status(filters_by_doctype=None):

    filters_by_doctype = json.loads(filters_by_doctype) if filters_by_doctype else {}
    results = {}

    for doctype, items in filters_by_doctype.items():

        parent_table = f"`tab{doctype}`"

        for item in items:

            name = item.get("name")
            if not name:
                continue

            parent_filters = item.get("filters", {})
            parent_conditions = []
            params = {}

            for key, val in parent_filters.items():

                # BETWEEN
                if isinstance(val, list) and val[0] == "between":
                    parent_conditions.append(
                        f"{parent_table}.`{key}` BETWEEN %({key}_start)s AND %({key}_end)s"
                    )
                    params[f"{key}_start"] = val[1][0]
                    params[f"{key}_end"] = val[1][1]

                # NOT EQUAL
                elif isinstance(val, list) and val[0] == "!=":
                    parent_conditions.append(
                        f"{parent_table}.`{key}` != %({key})s"
                    )
                    params[key] = val[1]

                # EQUAL
                else:
                    parent_conditions.append(
                        f"{parent_table}.`{key}` = %({key})s"
                    )
                    params[key] = val

            where_sql = " AND ".join(parent_conditions) or "1=1"

            sql = f"""
                SELECT status
                FROM {parent_table}
                WHERE {where_sql}
                ORDER BY creation DESC
                LIMIT 1
            """

            row = frappe.db.sql(sql, params, as_dict=True)

            results[name] = row[0]["status"] if row else None

    return results
# import frappe
# import json

# @frappe.whitelist()
# def count_records(filters_by_doctype=None):
  
#     """
#     Count records per Doctype with custom names.

#     Example payload:
#     {
#       "Members": [
#         {"name": "total_petitioner", "filters": {"overall_status": "PETITIONER"}},
#         {"name": "total_apprentice", "filters": {"overall_status": "APPRENTICE"}}
#       ],
#       "Sales Invoice": [
#         {"name": "paid_invoices", "filters": {"status": "Paid"}}
#       ]
#     }
#     """
#     filters_by_doctype = json.loads(filters_by_doctype) if filters_by_doctype else {}

#     results = {}

#     for doctype, items in filters_by_doctype.items():
#         parent_table = f"`tab{doctype}`"
#         print("doctype: ", doctype)
#         for item in items:
#             name = item.get("name")
#             parent_filters = item.get("filters", {})
#             child = item.get("child", None)

#             if not name: 
#                 continue

#             # ✅ Build Parent WHERE Clause
#             parent_conditions = []
#             params = {}

#             for key, val in parent_filters.items():
#                 if isinstance(val, list) and val[0] == "!=":
#                     parent_conditions.append(f"{parent_table}.`{key}` != %({key})s")
#                     params[key] = val[1]
#                 else:
#                     parent_conditions.append(f"{parent_table}.`{key}` = %({key})s")
#                     params[key] = val

#             parent_where = " AND ".join(parent_conditions) or "1=1"

#             # ✅ If no child required → simple count
#             if not child:
#                 sql = f"SELECT COUNT(*) as count FROM {parent_table} WHERE {parent_where}"
#                 results[name] = frappe.db.sql(sql, params, as_dict=True)[0]["count"]
#                 continue

#             # ✅ Child logic (include / exclude)
#             child_table = f"`tab{child['doctype']}`"
#             child_filters = child.get("filters", {})
#             child_conditions = []

#             for key, val in child_filters.items():
#                 if isinstance(val, list) and val[0] == "!=":
#                     child_conditions.append(f"{child_table}.`{key}` != %({key})s")
#                     params[key] = val[1]
#                 else:
#                     child_conditions.append(f"{child_table}.`{key}` = %({key})s")
#                     params[key] = val

#             child_where = " AND ".join(child_conditions) or "1=1"

#             # ✅ Include child rows (JOIN)
#             if not child.get("exclude", False):
#                 sql = f"""
#                     SELECT COUNT(DISTINCT {parent_table}.name) AS count
#                     FROM {parent_table}
#                     INNER JOIN {child_table}
#                     ON {parent_table}.name = {child_table}.parent
#                     WHERE {parent_where} AND {child_where}
#                 """
#             else:
#                 # ✅ Exclude → parent records with NO matching child
#                 sql = f"""
#                     SELECT COUNT(*) as count
#                     FROM {parent_table}
#                     WHERE {parent_where}
#                     AND {parent_table}.name NOT IN (
#                         SELECT DISTINCT parent FROM {child_table} WHERE {child_where}
#                     )
#                 """

#             results[name] = frappe.db.sql(sql, params, as_dict=True)[0]["count"]

#     return results
