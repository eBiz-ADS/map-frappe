import frappe
import json
from datetime import datetime, date
import calendar
import re

def normalize_date(date_str: str) -> str:
    """
    Convert 'MM-DD-YYYY' to 'YYYY-MM-DD'.
    If the string is already in 'YYYY-MM-DD', returns it unchanged.
    """
    parts = date_str.strip().split("%")
    parts = parts[1].strip().split("-")
    if len(parts) == 3:
        # Check if first part is length 2 (MM), last part is length 4 (YYYY)
        if len(parts[0]) == 2 and len(parts[2]) == 4:
            mm, dd, yyyy = parts
            return f"{yyyy}-{mm}-{dd}"
    return date_str  # return unchanged if not matching

@frappe.whitelist()
def search_members(filters: str = "[]", search: str = "", limit: int = None,
                   limit_start: int = 0, order_by: str = "full_name asc"):
    # -------------------------------
    # Load filters
    # -------------------------------
    try:
        filters_list = json.loads(filters)
    except Exception:
        filters_list = []

    where_clauses = []
    params = []

    # -------------------------------
    # Child Table Field Mapping
    # -------------------------------
    child_field_map = {
        # Payment child table fields
        "or_number": ("tabPayment", "or_number"),
        "year": ("tabPayment", "year"),
        "amount": ("tabPayment", "amount"),
        "date_of_payment": ("tabPayment", "date_of_payment"),

        # Activities child table fields
        # (activities_date → date, etc.)
        "activities_date": ("tabActivities", "date"),
        "activities_type": ("tabActivities", "type"),
        "activities_action": ("tabActivities", "action"),
        "activities_notes": ("tabActivities", "notes"),
    }

    # -------------------------------
    # Process each filter (AND conditions)
    # -------------------------------
    for f in filters_list:
        if not isinstance(f, list) or len(f) != 3:
            continue

        field, condition, value = f
        normalized_field = field.lower().strip()
        condition_upper = condition.upper()

        # -------------------------------
        # CHILD TABLE FILTER
        # -------------------------------
        if normalized_field in child_field_map:
            child_table, child_col = child_field_map[normalized_field]

            # Normalize date if it's a date field
            if normalized_field in ["activities_date", "date_of_payment"]:
                value = normalize_date(str(value))
                

            # IN / NOT IN
            if condition_upper in ["IN", "NOT IN"]:
                if isinstance(value, list):
                    placeholders = ", ".join(["%s"] * len(value))
                    where_clauses.append(f"""
                        EXISTS (
                            SELECT 1 FROM `{child_table}`
                            WHERE parent = `tabMembers`.name
                            AND `{child_col}` {condition_upper} ({placeholders})
                        )
                    """)
                    params.extend(value)
                else:
                    where_clauses.append(f"""
                        EXISTS (
                            SELECT 1 FROM `{child_table}`
                            WHERE parent = `tabMembers`.name
                            AND `{child_col}` {condition_upper} (%s)
                        )
                    """)
                    params.append(value)
            else:
                # normal filter
                where_clauses.append(f"""
                    EXISTS (
                        SELECT 1 FROM `{child_table}`
                        WHERE parent = `tabMembers`.name
                        AND {f'`{child_col}`' if normalized_field not in ["activities_date","date_of_payment"] else f'DATE(`{child_col}`)'} {condition} %s
                    )
                """)
                params.append(value)

            continue  # move to next filter

        # -------------------------------
        # NORMAL PARENT FILTER
        # -------------------------------
        # Special case: overall_status = "Inactive"
        if field == "overall_status" and str(value).strip().lower() == "%inactive%":
            inactive_statuses = ["SNPD", "DIED", "EXPELLED", "DROPPED"] 
            placeholders = ", ".join(["%s"] * len(inactive_statuses))
            where_clauses.append(f"overall_status IN ({placeholders})")
            params.extend(inactive_statuses)
            continue

        # Normalize date fields
        if field.lower() in ["date_raised", "date_passed", "date_initiated"]:
            value = normalize_date(str(value))
            where_clauses.append(f"DATE(`{field}`) {condition} %s")
            params.append(value)
            continue

        # IN / NOT IN
        if condition_upper in ["IN", "NOT IN"]:
            if isinstance(value, list):
                placeholders = ", ".join(["%s"] * len(value))
                where_clauses.append(f"`{field}` {condition_upper} ({placeholders})")
                params.extend(value)
            else:
                where_clauses.append(f"`{field}` {condition_upper} (%s)")
                params.append(value)
        else:
            where_clauses.append(f"`{field}` {condition} %s")
            params.append(value)

    # -------------------------------
    # OR SEARCH
    # -------------------------------
    if search:
        search_lower = str(search).lower()
        search_param = f"%{search_lower}%"
        or_parts = [
            "LOWER(full_name) LIKE %s",
            "LOWER(position) LIKE %s",
            "LOWER(overall_status) LIKE %s",
            "CAST(TIMESTAMPDIFF(YEAR, date_raised, CURDATE()) AS CHAR) LIKE %s"
        ]
        where_clauses.append("(" + " OR ".join(or_parts) + ")")
        params.extend([search_param] * 4)

    # -------------------------------
    # OR status filter
    # -------------------------------
    # where_clauses.append(
    #     "(LOWER(overall_status) LIKE '%%active%%' OR LOWER(overall_status) LIKE '%%demitted%%')"
    # )

    # -------------------------------
    # Final WHERE SQL
    # -------------------------------
    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    # -------------------------------
    # COUNT MODE
    # -------------------------------
    if not limit:
        count = frappe.db.sql(
            f"""
            SELECT COUNT(*) AS total
            FROM `tabMembers`
            WHERE {where_sql}
            """,
            params,
            as_dict=True
        )
        return {"count": count[0].total}

    # -------------------------------
    # PAGINATION MODE
    # -------------------------------
    data = frappe.db.sql(
        f"""
        SELECT
            name, member_key, id_number, full_name, date_raised,
            overall_status, district, lodge
        FROM `tabMembers`
        WHERE {where_sql}
        ORDER BY {order_by}
        LIMIT %s OFFSET %s
        """,
        params + [limit, limit_start],
        as_dict=True
    )

    # Fetch masonic_service_records child rows in one query
    if data:
        names = [r["name"] for r in data]
        placeholders = ", ".join(["%s"] * len(names))
        records = frappe.db.sql(
            f"""
            SELECT parent, record_type, record_value, lodge_no, lodge_name, date_encoded, additional_info, date_official, record, record_encoder
            FROM `tabMasonic Service Records`
            WHERE parent IN ({placeholders})
            ORDER BY creation ASC
            """,
            names,
            as_dict=True
        )

        # Group by parent
        records_map = {}
        for record in records:
            records_map.setdefault(record["parent"], []).append(record)

        for row in data:
            row["masonic_service_records"] = records_map.get(row["name"], [])

    return {"data": data}

@frappe.whitelist()
def search_petitioners(filters: str = "[]", search: str = "", limit: int = None,
                   limit_start: int = 0, order_by: str = "full_name asc"):
    # -------------------------------
    # Load filters
    # -------------------------------
    try:
        filters_list = json.loads(filters)
    except Exception:
        filters_list = []

    where_clauses = []
    params = []

    # -------------------------------
    # Child Table Field Mapping
    # -------------------------------
    child_field_map = {
        # Payment child table fields
        "or_number": ("tabPayment", "or_number"),
        "year": ("tabPayment", "year"),
        "amount": ("tabPayment", "amount"),
        "date_of_payment": ("tabPayment", "date_of_payment"),

        # Activities child table fields
        # (activities_date → date, etc.)
        "activities_date": ("tabActivities", "date"),
        "activities_type": ("tabActivities", "type"),
        "activities_action": ("tabActivities", "action"),
        "activities_notes": ("tabActivities", "notes"),
    }

    # -------------------------------
    # Process each filter (AND conditions)
    # -------------------------------
    for f in filters_list:
        if not isinstance(f, list) or len(f) != 3:
            continue

        field, condition, value = f
        normalized_field = field.lower().strip()
        condition_upper = condition.upper()

        # -------------------------------
        # CHILD TABLE FILTER
        # -------------------------------
        if normalized_field in child_field_map:
            child_table, child_col = child_field_map[normalized_field]

            # Normalize date if it's a date field
            if normalized_field in ["activities_date", "date_of_payment"]:
                value = normalize_date(str(value))
                

            # IN / NOT IN
            if condition_upper in ["IN", "NOT IN"]:
                if isinstance(value, list):
                    placeholders = ", ".join(["%s"] * len(value))
                    where_clauses.append(f"""
                        EXISTS (
                            SELECT 1 FROM `{child_table}`
                            WHERE parent = `tabPetitioners List`.name
                            AND `{child_col}` {condition_upper} ({placeholders})
                        )
                    """)
                    params.extend(value)
                else:
                    where_clauses.append(f"""
                        EXISTS (
                            SELECT 1 FROM `{child_table}`
                            WHERE parent = `tabPetitioners List`.name
                            AND `{child_col}` {condition_upper} (%s)
                        )
                    """)
                    params.append(value)
            else:
                # normal filter
                where_clauses.append(f"""
                    EXISTS (
                        SELECT 1 FROM `{child_table}`
                        WHERE parent = `tabPetitioners List`.name
                        AND {f'`{child_col}`' if normalized_field not in ["activities_date","date_of_payment"] else f'DATE(`{child_col}`)'} {condition} %s
                    )
                """)
                params.append(value)

            continue  # move to next filter

        # -------------------------------
        # NORMAL PARENT FILTER
        # -------------------------------
        # Special case: overall_status = "Inactive"
        if field == "overall_status" and str(value).strip().lower() == "%inactive%":
            inactive_statuses = ["SNPD", "DIED", "EXPELLED", "DROPPED"] 
            placeholders = ", ".join(["%s"] * len(inactive_statuses))
            where_clauses.append(f"overall_status IN ({placeholders})")
            params.extend(inactive_statuses)
            continue

        # Normalize date fields
        if field.lower() in ["date_raised", "date_passed", "date_initiated"]:
            value = normalize_date(str(value))
            where_clauses.append(f"DATE(`{field}`) {condition} %s")
            params.append(value)
            continue

        # IN / NOT IN
        if condition_upper in ["IN", "NOT IN"]:
            if isinstance(value, list):
                placeholders = ", ".join(["%s"] * len(value))
                where_clauses.append(f"`{field}` {condition_upper} ({placeholders})")
                params.extend(value)
            else:
                where_clauses.append(f"`{field}` {condition_upper} (%s)")
                params.append(value)
        else:
            where_clauses.append(f"`{field}` {condition} %s")
            params.append(value)

    # -------------------------------
    # OR SEARCH
    # -------------------------------
    if search:
        search_lower = str(search).lower()
        search_param = f"%{search_lower}%"
        or_parts = [
            "LOWER(full_name) LIKE %s",
            "LOWER(position) LIKE %s",
            "LOWER(overall_status) LIKE %s",
            "CAST(TIMESTAMPDIFF(YEAR, date_raised, CURDATE()) AS CHAR) LIKE %s"
        ]
        where_clauses.append("(" + " OR ".join(or_parts) + ")")
        params.extend([search_param] * 4)

    # -------------------------------
    # OR status filter
    # -------------------------------
    # where_clauses.append(
    #     "(LOWER(overall_status) LIKE '%%active%%' OR LOWER(overall_status) LIKE '%%demitted%%')"
    # )

    # -------------------------------
    # Final WHERE SQL
    # -------------------------------
    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    # -------------------------------
    # COUNT MODE
    # -------------------------------
    if not limit:
        count = frappe.db.sql(
            f"""
            SELECT COUNT(*) AS total
            FROM `tabPetitioners List`
            WHERE {where_sql}
            """,
            params,
            as_dict=True
        )
        return {"count": count[0].total}

    # -------------------------------
    # PAGINATION MODE
    # -------------------------------
    data = frappe.db.sql(
        f"""
        SELECT
            name, member_key, full_name, date_raised,
            overall_status, district, lodge
        FROM `tabPetitioners List`
        WHERE {where_sql}
        ORDER BY {order_by}
        LIMIT %s OFFSET %s
        """,
        params + [limit, limit_start],
        as_dict=True
    )

  # Fetch masonic_service_records child rows in one query
    if data:
        names = [r["name"] for r in data]
        placeholders = ", ".join(["%s"] * len(names))
        records = frappe.db.sql(
            f"""
            SELECT parent, record_type, record_value, lodge_no, lodge_name, date_encoded, additional_info, date_official, record, record_encoder
            FROM `tabMasonic Service Records`
            WHERE parent IN ({placeholders})
            ORDER BY creation ASC
            """,
            names,
            as_dict=True
        )

        # Group by parent
        records_map = {}
        for record in records:
            records_map.setdefault(record["parent"], []).append(record)

        for row in data:
            row["masonic_service_records"] = records_map.get(row["name"], [])


    return {"data": data}

@frappe.whitelist()
def search_district(search: str = "", limit: int = None,
                   limit_start: int = 0, order_by: str = "district asc"):

    where_clauses = []
    params = []

    # -------------------------------
    # OR SEARCH
    # -------------------------------
    if search:
        search_lower = str(search).lower()
        search_param = f"%{search_lower}%"
        or_parts = [
            "LOWER(district) LIKE %s",
            "LOWER(district_code) LIKE %s",
            "LOWER(institution_date) LIKE %s",
            "LOWER(status) LIKE %s",
            "LOWER(location) LIKE %s"
        ]
        where_clauses.append("(" + " OR ".join(or_parts) + ")")
        params.extend([search_param] * 5)

    # Final WHERE clause
    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    # -------------------------------
    # COUNT MODE
    # -------------------------------
    if not limit:
        count = frappe.db.sql(f"""
            SELECT COUNT(*) AS total
            FROM `tabDistrict`
            WHERE {where_sql}
        """, params, as_dict=True)
        return {"count": count[0].total}

    # -------------------------------
    # PAGINATION MODE
    # -------------------------------
    data = frappe.db.sql(f"""
        SELECT
            district, district_code, institution_date, status, location, name
        FROM `tabDistrict`
        WHERE {where_sql}
        ORDER BY {order_by}
        LIMIT %s OFFSET %s
    """, params + [limit, limit_start], as_dict=True)

    return {"data": data}


@frappe.whitelist()
def search_lodge(search: str = "", limit: int = None,
                   limit_start: int = 0, order_by: str = "lodge_name asc"):

    try:
        where_clauses = []
        params = []

        # -------------------------------
        # OR SEARCH
        # -------------------------------
        if search:
            search_lower = str(search).lower()
            search_param = f"%{search_lower}%"
            or_parts = [
                "LOWER(lodge_no) LIKE %s",
                "LOWER(lodge_name) LIKE %s",
                "LOWER(lodge_district) LIKE %s",
                # "LOWER(status) LIKE %s",
                "LOWER(location) LIKE %s",
                # "LOWER(institution_date) LIKE %s"
            ]
            where_clauses.append("(" + " OR ".join(or_parts) + ")")
            params.extend([search_param] * 6)

        # Final WHERE clause
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        # -------------------------------
        # COUNT MODE
        # -------------------------------
        if not limit:
            count = frappe.db.sql(f"""
                SELECT COUNT(*) AS total
                FROM `tabLodge List`
                WHERE {where_sql}
            """, params, as_dict=True)
            return {"count": count[0].total}

        # -------------------------------
        # PAGINATION MODE
        # -------------------------------
        data = frappe.db.sql(f"""
            SELECT
                lodge_no, lodge_name, district, district_name, status,
                location, institution_date, name, district_id_code
            FROM `tabLodge List`
            WHERE {where_sql}
            ORDER BY {order_by}
            LIMIT %s OFFSET %s
        """, params + [limit, limit_start], as_dict=True)

        return {"data": data}
    except Exception as e:
        frappe.log_error(f"search_lodge error: {frappe.get_traceback()}")
        raise e

def get_date_completed_range(filter_value: str):
    today = date.today()
    day = today.day
    month = today.month
    year = today.year

    # Identify today's bucket
    if 10 <= day <= 19:
        today_bucket = "A"
    elif 20 <= day <= 29:
        today_bucket = "B"
    else:
        today_bucket = "C"

    # Bucket definitions (day ranges)
    buckets = {
        "A": (10, 19),
        "B": (20, 29),
        "C": ("C", "C"),  # special: 30–31 OR 1–9
    }

    # Determine target bucket
    if filter_value == "for publish":
        target_bucket = today_bucket
    elif filter_value == "published":
        target_bucket = {
            "A": "C",
            "B": "A",
            "C": "B",
        }[today_bucket]
    else:
        return None

    # --- Calculate date ranges ---
    if target_bucket == "C":
        # Bucket C = 30–31 previous month + 1–9 current month
        if month == 1:
            # January → previous month is December of last year
            prev_month = 12
            prev_year = year - 1
        else:
            prev_month = month - 1
            prev_year = year

        # Start date = 30th of previous month
        start_date = date(prev_year, prev_month, 30)
        # End date = 9th of current month
        end_date = date(year, month, 9)
    else:
        # Bucket A or B = only current month
        if target_bucket == "A":
            start_day, end_day = 10, 19
        else:  # B
            start_day, end_day = 20, 29
        start_date = date(year, month, start_day)
        end_date = date(year, month, end_day)

    # Return SQL condition
    return f"(date_completed BETWEEN '{start_date}' AND '{end_date}')"


# OLD NEED CLARIFICATION
# def get_date_completed_circular():
#     today = date.today()
#     day = today.day
#     month = today.month
#     year = today.year

#     # Determine today's bucket
#     if 10 <= day <= 19:
#         today_bucket = "A"
#     elif 20 <= day <= 29:
#         today_bucket = "B"
#     else:  # 30/31/1–9
#         today_bucket = "C"

#     prev_bucket = {"A": "C", "B": "A", "C": "B"}[today_bucket]

#     # Previous month logic
#     if month == 1:
#         prev_month = 12
#         prev_year = year - 1
#     else:
#         prev_month = month - 1
#         prev_year = year

#     # -------- Calculate Date Range --------

#     if prev_bucket == "A":
#         # 10–19
#         # Same month if today is B
#         if today_bucket == "B":
#             start_date = date(year, month, 10)
#             end_date = date(year, month, 19)
#         else:
#             start_date = date(prev_year, prev_month, 10)
#             end_date = date(prev_year, prev_month, 19)

#     elif prev_bucket == "B":
#         # 20–29
#         if today_bucket == "C":
#             # Must use previous month
#             last_day = min(29, calendar.monthrange(prev_year, prev_month)[1])
#             start_date = date(prev_year, prev_month, 20)
#             end_date = date(prev_year, prev_month, last_day)
#         else:
#             last_day = min(29, calendar.monthrange(year, month)[1])
#             start_date = date(year, month, 20)
#             end_date = date(year, month, last_day)

#     else:  # prev_bucket == "C"
#         # 30/31 previous month + 1–9 current month
#         last_day_prev = calendar.monthrange(prev_year, prev_month)[1]
#         start_day = 30 if last_day_prev >= 30 else last_day_prev
#         start_date = date(prev_year, prev_month, start_day)
#         end_date = date(year, month, 9)

#     return f"(date_completed BETWEEN '{start_date}' AND '{end_date}')"

# NEW NEED CLARIFICATION
def get_date_completed_circular():
    today = date.today()

    year = today.year
    month = today.month
    day = today.day

    if 1 <= day <= 10:
        start_date = date(year, month, 1)
        end_date = date(year, month, 10)

    elif 11 <= day <= 20:
        start_date = date(year, month, 11)
        end_date = date(year, month, 20)

    else:  # 21 → end of month
        last_day = calendar.monthrange(year, month)[1]
        start_date = date(year, month, 21)
        end_date = date(year, month, last_day)

    return f"(date_completed BETWEEN '{start_date}' AND '{end_date}')"
# def get_date_completed_circular_members():
#     today = date.today()
#     month = today.month
#     year = today.year
    
#     start_date = date(year, month, 1)
#     last_day = min(29, calendar.monthrange(year, month)[1])
#     end_date = date(year, month, last_day)

#     # Return SQL condition
#     return f"(date BETWEEN '{start_date}' AND '{end_date}')"

def get_date_completed_circular_members():
    today = date.today()
    month = today.month
    year = today.year

    start_date = date(year, month, 1)
    end_date = date(year, month, calendar.monthrange(year, month)[1])

    return f"""
        EXISTS (
            SELECT 1
            FROM `tabHistory Logs` h
            WHERE h.parent = `tabMonthly Member Report`.name
            AND h.action = 'For Publish'
            AND DATE(h.date_completed)
                BETWEEN '{start_date}' AND '{end_date}'
        )
    """


@frappe.whitelist()
def search_petition(filters: str = "[]", search: str = "", limit: int = None,
                   limit_start: int = 0, order_by: str = "name asc"):
    # -------------------------------
    # Load filters
    # -------------------------------
    try:
        filters_list = json.loads(filters)
    except Exception:
        filters_list = []

    where_clauses = []
    params = []

    # -------------------------------
    # Child Table Field Mapping
    # -------------------------------
    child_field_map = {
        # Payment child table fields
        "date_of_birth": ("tabPetitioners List", "date_of_birth"),
    }

    # -------------------------------
    # Process each filter (AND conditions)
    # -------------------------------
    for f in filters_list:
        if not isinstance(f, list) or len(f) != 3:
            continue

        field, condition, value = f
        normalized_field = field.lower().strip()
        condition_upper = condition.upper()

        # -------------------------------
        # DATE_COMPLETED + STATUS LOGIC
        # -------------------------------
        if normalized_field == "date_completed":

            normalized_value = str(value).lower().replace("%", "").strip()

            if normalized_value in ["published", "for publish"]:
                date_condition = get_date_completed_range(normalized_value)
                if date_condition:
                    where_clauses.append(date_condition)
                continue
        # -------------------------------
        # CHILD TABLE FILTER
        # -------------------------------
        if normalized_field in child_field_map:
            child_table, child_col = child_field_map[normalized_field]

            # Normalize date if it's a date field
            if normalized_field in ["date_of_birth"]:
                value = normalize_date(str(value))
                

            # IN / NOT IN
            if condition_upper in ["IN", "NOT IN"]:
                if isinstance(value, list):
                    placeholders = ", ".join(["%s"] * len(value))
                    where_clauses.append(f"""
                        EXISTS (
                            SELECT 1 FROM `{child_table}`
                            WHERE `petitioner` = `tabPetitions`.name
                            AND `{child_col}` {condition_upper} ({placeholders})
                        )
                    """)

                    params.extend(value)
                else:
                    where_clauses.append(f"""
                        EXISTS (
                            SELECT 1 FROM `{child_table}`
                            WHERE `petitioner` = `tabPetitions`.name
                            AND `{child_col}` {condition_upper} (%s)
                        )
                    """)
                    params.append(value)
            else:
                # normal filter
                where_clauses.append(f"""
                    EXISTS (
                        SELECT 1 FROM `{child_table}`
                        WHERE `petitioner` = `tabPetitions`.name
                        AND {f'`{child_col}`' if normalized_field not in ["date_of_birth"] else f'DATE(`{child_col}`)'} {condition} %s
                    )
                """)
                params.append(value)

            continue  # move to next filter

        # -------------------------------
        # NORMAL PARENT FILTER
        # -------------------------------
        # Normalize date fields
        if field.lower() in ["created"]:
            value = normalize_date(str(value))
            where_clauses.append(f"DATE(`{field}`) {condition} %s")
            params.append(value)
            continue

        # IN / NOT IN
        if condition_upper in ["IN", "NOT IN"]:
            if isinstance(value, list):
                placeholders = ", ".join(["%s"] * len(value))
                where_clauses.append(f"`{field}` {condition_upper} ({placeholders})")
                params.extend(value)
            else:
                where_clauses.append(f"`{field}` {condition_upper} (%s)")
                params.append(value)
        else:
            where_clauses.append(f"`{field}` {condition} %s")
            params.append(value)

    # -------------------------------
    # OR SEARCH
    # -------------------------------
    if search:
        search_lower = str(search).lower()
        search_param = f"%{search_lower}%"
        or_parts = [
            "LOWER(name) LIKE %s",
            "LOWER(petitioner_name) LIKE %s",
            "LOWER(status) LIKE %s",
            "LOWER(new_lodge) LIKE %s",
            "LOWER(type) LIKE %s",
        ]
        where_clauses.append("(" + " OR ".join(or_parts) + ")")
        params.extend([search_param] * 5)

    # -------------------------------
    # OR status filter
    # -------------------------------
    # where_clauses.append(
    #     "(LOWER(overall_status) LIKE '%%active%%' OR LOWER(overall_status) LIKE '%%demitted%%')"
    # )

    # -------------------------------
    # Final WHERE SQL
    # -------------------------------
    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    # -------------------------------
    # COUNT MODE
    # -------------------------------
    if not limit:
        count = frappe.db.sql(
            f"""
            SELECT COUNT(*) AS total
            FROM `tabPetitions`
            WHERE {where_sql}
            """,
            params,
            as_dict=True
        )
        return {"count": count[0].total}

    # -------------------------------
    # PAGINATION MODE
    # -------------------------------
    data = frappe.db.sql(
        f"""
        SELECT
            name, status, type, petitioner_name, new_lodge, new_lodge_no, new_lodge_name, type, petitioner, creation, presented, elected, date_of_birth, residence_address, occupation, member_name, member
        FROM `tabPetitions`
        WHERE {where_sql}
        ORDER BY {order_by}
        LIMIT %s OFFSET %s
        """,
        params + [limit, limit_start],
        as_dict=True
    )

    # Fetch history_logs child rows in one query
    if data:
        names = [r["name"] for r in data]
        placeholders = ", ".join(["%s"] * len(names))
        logs = frappe.db.sql(
            f"""
            SELECT parent, participant, action, remarks, date_completed
            FROM `tabHistory Logs`
            WHERE parent IN ({placeholders})
            ORDER BY creation ASC
            """,
            names,
            as_dict=True
        )

        # Group by parent
        logs_map = {}
        for log in logs:
            logs_map.setdefault(log["parent"], []).append(log)

        for row in data:
            row["history_logs"] = logs_map.get(row["name"], [])


    return {"data": data}


@frappe.whitelist()
def search_petition_circular():

    where_clauses = []

    where_clauses.append(
        "status IN ('FOR PUBLISH', 'REJECTED')"  # only these 2 statuses are relevant for circular
    )

    where_clauses.append(
        "(circular12_status IS NULL OR circular12_status NOT IN ('DRAFT', 'PUBLISHED'))"
    )  

    # -------------------------------
    # DATE_COMPLETED + STATUS LOGIC
    # -------------------------------

    date_condition = get_date_completed_circular()
    if date_condition:
        where_clauses.append(date_condition)

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    data = frappe.db.sql(
        f"""
        SELECT
            p.name, p.status, p.petitioner_name, p.new_lodge, p.type, p.presented, p.date_completed, p.new_lodge_no, p.new_lodge_name, p.petitioner,
            pt.occupation AS occupation,
            pt.short_residence_address AS short_residence_address,
            p.member, p.member_name
        FROM `tabPetitions` p
        LEFT JOIN `tabPetitioners List` pt
            ON pt.name = p.petitioner
        WHERE {where_sql}
        """,
        as_dict=True
    )

    return {"data": data,
            "date_condition": date_condition
            }

@frappe.whitelist()
def search_member_circular():

    where_clauses = []  # only these 2 statuses are relevant for circular
    
    # where_clauses.append(
    #     "status IN ('Completed')"  # only these 2 statuses are relevant for circular
    # )

    where_clauses.append(
        "(circular12_status IS NULL OR circular12_status NOT IN ('DRAFT', 'PUBLISHED'))"
    )  

    # where_clauses.append("status != 'Draft'") 
    where_clauses.append("status = 'For Publish'")

    # -------------------------------
    # DATE_COMPLETED + STATUS LOGIC
    # -------------------------------

    date_condition = get_date_completed_circular_members()
    if date_condition:
        where_clauses.append(date_condition)

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    data = frappe.db.sql(
        f"""
        SELECT name
        FROM `tabMonthly Member Report` 
        WHERE {where_sql}
        """,
        as_dict=True
    )

    result = []

    for p in data: 
        doc = frappe.get_doc("Monthly Member Report", p.name)

        result.append({
            "name": doc.name,
            "status": doc.status,
            "lodge_name": doc.lodge_name,
            "lodge_no": doc.lodge_no,
            "date": doc.date,
            "restored": doc.restored,
            "petition_for_degrees_received": doc.petition_for_degrees_received,
            "petition_for_degrees_elected": doc.petition_for_degrees_elected,
            "petition_for": doc.petition_for,
            "petitions_for_affiliation_received": doc.petitions_for_affiliation_received,
            "petitions_for_affiliation_approved": doc.petitions_for_affiliation_approved,
            "petitions_for_affiliation_rejected": doc.petitions_for_affiliation_rejected,
            "iniated": doc.initiated,
            "passed": doc.passed,
            "raised": doc.raised,
            "snpd": doc.snpd,
            "sna": doc.sna,
            "sfc_suspended_for_a_cause": doc.sfc_suspended_for_a_cause,
            "other_suspension": doc.other_suspension,
            "given_dimit": doc.given_dimit,
            "died": doc.died,
            "expelled": doc.expelled,
            "dropped_from_the_roll": doc.dropped_from_the_roll            
        })

    return {"data": result}


def search_event_members(filters: str = "[]", search: str = "", limit: int = None,
                   limit_start: int = 0, order_by: str = "full_name asc"):

    import json

    try:
        filters_list = json.loads(filters)
    except Exception:
        filters_list = []

    where_clauses = []
    params = []

    # -------------------------------
    # AND FILTERS
    # -------------------------------
    for f in filters_list:
        # ensure filter is valid
        if not isinstance(f, list) or len(f) != 3:
            continue

        field, condition, value = f

        # Normal filter
        if condition.upper() in ["IN", "NOT IN"]:
            # handle IN clauses correctly
            if isinstance(value, list):
                placeholders = ", ".join(["%s"] * len(value))
                where_clauses.append(f"`{field}` {condition} ({placeholders})")
                params.extend(value)
            else:
                # fallback if value is not list
                where_clauses.append(f"`{field}` {condition} (%s)")
                params.append(value)
        else:
            where_clauses.append(f"`{field}` {condition} %s")
            params.append(value)

    # -------------------------------
    # OR 
    # -------------------------------
    or_parts = [
        "LOWER(overall_status) LIKE %ACTIVE",
        "LOWER(overall_status) LIKE %DEMITTED"
    ]
    where_clauses.append("(" + " OR ".join(or_parts) + ")")
    params.extend(2)

    # Final WHERE clause
    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    # -------------------------------
    # COUNT MODE
    # -------------------------------
    if not limit:
        count = frappe.db.sql(f"""
            SELECT COUNT(*) AS total
            FROM `tabMembers`
            WHERE {where_sql}
        """, params, as_dict=True)
        return {"count": count[0].total}

    # -------------------------------
    # PAGINATION MODE
    # -------------------------------
    data = frappe.db.sql(f"""
        SELECT
            name, member_key, full_name, date_raised,
            overall_status, district, lodge
        FROM `tabMembers`
        WHERE {where_sql}
        ORDER BY {order_by}
        LIMIT %s OFFSET %s
    """, params + [limit, limit_start], as_dict=True)

    return {"data": data}
    
@frappe.whitelist()
def search_regional(
    search: str = "",
    limit: int = None,
    limit_start: int = 0,
    order_by: str = "region asc"
):
    try:
        filters = []

        # -------------------------------
        # SEARCH (Regional only)
        # -------------------------------
        if search:
            filters.append(["region", "like", f"%{search}%"])

        # -------------------------------
        # COUNT MODE
        # -------------------------------
        if not limit:
            total = frappe.db.count("Regional", filters=filters)
            return {"count": total}

        # -------------------------------
        # PAGINATION (Parent only)
        # -------------------------------
        regionals = frappe.get_all(
            "Regional",
            filters=filters,
            fields=["name", "region"],
            order_by=order_by,
            limit_start=limit_start,
            limit_page_length=limit,
        )

        # -------------------------------
        # FETCH FULL DOCS (with children)
        # -------------------------------
        data = []
        for r in regionals:
            doc = frappe.get_doc("Regional", r.name)

            data.append({
                "name": doc.name,
                "region": doc.region,
                "districts": doc.districts  # CHILD TABLE FIELDNAME
            })

        return {"data": data}

    except Exception:
        frappe.log_error(frappe.get_traceback(), "search_regional error")
        frappe.throw("Unable to fetch Regional data")

@frappe.whitelist()
def search_change_request(filters: str = "[]", search: str = "", limit: int = None,
                   limit_start: int = 0, order_by: str = "name asc"):
    # -------------------------------
    # Load filters
    # -------------------------------
    try:
        filters_list = json.loads(filters)
    except Exception:
        filters_list = []

    where_clauses = []
    params = []

    # -------------------------------
    # Process each filter (AND conditions)
    # -------------------------------
    for f in filters_list:
        if not isinstance(f, list) or len(f) != 3:
            continue

        field, condition, value = f
        condition_upper = condition.upper()

        # -------------------------------
        # NORMAL PARENT FILTER
        # -------------------------------
        # Normalize date fields
        if field.lower() in ["created"]:
            value = normalize_date(str(value))
            where_clauses.append(f"DATE(`{field}`) {condition} %s")
            params.append(value)
            continue

        # IN / NOT IN
        if condition_upper in ["IN", "NOT IN"]:
            if isinstance(value, list):
                placeholders = ", ".join(["%s"] * len(value))
                where_clauses.append(f"`{field}` {condition_upper} ({placeholders})")
                params.extend(value)
            else:
                where_clauses.append(f"`{field}` {condition_upper} (%s)")
                params.append(value)
        else:
            where_clauses.append(f"`{field}` {condition} %s")
            params.append(value)

    # -------------------------------
    # OR SEARCH
    # -------------------------------
    if search:
        search_lower = str(search).lower()
        search_param = f"%{search_lower}%"
        or_parts = [
            "LOWER(name) LIKE %s",
            "LOWER(full_name) LIKE %s",
            "LOWER(lodge) LIKE %s",
            "LOWER(reason) LIKE %s",
        ]
        where_clauses.append("(" + " OR ".join(or_parts) + ")")
        params.extend([search_param] * 5)

    # -------------------------------
    # OR status filter
    # -------------------------------
    # where_clauses.append(
    #     "(LOWER(overall_status) LIKE '%%active%%' OR LOWER(overall_status) LIKE '%%demitted%%')"
    # )

    # -------------------------------
    # Final WHERE SQL
    # -------------------------------
    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    # -------------------------------
    # COUNT MODE
    # -------------------------------
    if not limit:
        count = frappe.db.sql(
            f"""
            SELECT COUNT(*) AS total
            FROM `tabChange Request`
            WHERE {where_sql}
            """,
            params,
            as_dict=True
        )
        return {"count": count[0].total}

    # -------------------------------
    # PAGINATION MODE
    # -------------------------------
    data = frappe.db.sql(
        f"""
        SELECT
            name, member, full_name, lodge, reason, status, action_date
        FROM `tabChange Request`
        WHERE {where_sql}
        ORDER BY {order_by}
        LIMIT %s OFFSET %s
        """,
        params + [limit, limit_start],
        as_dict=True
    )

# Fetch change_request_fields child rows in one query
    if data:
        names = [r["name"] for r in data]
        placeholders = ", ".join(["%s"] * len(names))
        field_rows = frappe.db.sql(
            f"""
            SELECT parent, category, field_name, new_value, status, name
            FROM `tabChange Request Fields`
            WHERE parent IN ({placeholders})
            ORDER BY creation ASC
            """,
            names,
            as_dict=True
        )

        # Group by parent
        field_rows_map = {}
        for field in field_rows:
            field_rows_map.setdefault(field["parent"], []).append(field)

        for row in data:
            row["change_request_fields"] = field_rows_map.get(row["name"], [])

    return {"data": data}

@frappe.whitelist()
def search_circular12(filters: str = "[]", search: str = "", limit: int = None,
                   limit_start: int = 0, order_by: str = "name asc"):
    # -------------------------------
    # Load filters
    # -------------------------------
    try:
        filters_list = json.loads(filters)
    except Exception:
        filters_list = []

    where_clauses = []
    params = []

    # -------------------------------
    # Process each filter (AND conditions)
    # -------------------------------
    for f in filters_list:
        if not isinstance(f, list) or len(f) != 3:
            continue

        field, condition, value = f
        normalized_field = field.lower().strip()
        condition_upper = condition.upper()

        # -------------------------------
        # NORMAL PARENT FILTER
        # -------------------------------

        # Normalize date fields
        if field.lower() in ["date_created"]:
            value = normalize_date(str(value))
            where_clauses.append(f"DATE(`{field}`) {condition} %s")
            params.append(value)
            continue

        # IN / NOT IN
        if condition_upper in ["IN", "NOT IN"]:
            if isinstance(value, list):
                placeholders = ", ".join(["%s"] * len(value))
                where_clauses.append(f"`{field}` {condition_upper} ({placeholders})")
                params.extend(value)
            else:
                where_clauses.append(f"`{field}` {condition_upper} (%s)")
                params.append(value)
        else:
            where_clauses.append(f"`{field}` {condition} %s")
            params.append(value)

    # -------------------------------
    # OR SEARCH
    # -------------------------------
    if search:
        search_lower = str(search).lower()
        search_param = f"%{search_lower}%"
        or_parts = [
            "LOWER(name) LIKE %s",
            "LOWER(status) LIKE %s"
            # "CAST(TIMESTAMPDIFF(YEAR, date_raised, CURDATE()) AS CHAR) LIKE %s"
        ]
        where_clauses.append("(" + " OR ".join(or_parts) + ")")
        params.extend([search_param] * 4)

    # -------------------------------
    # OR status filter
    # -------------------------------
    # where_clauses.append(
    #     "(LOWER(overall_status) LIKE '%%active%%' OR LOWER(overall_status) LIKE '%%demitted%%')"
    # )

    # -------------------------------
    # Final WHERE SQL
    # -------------------------------
    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    # -------------------------------
    # COUNT MODE
    # -------------------------------
    if not limit:
        count = frappe.db.sql(
            f"""
            SELECT COUNT(*) AS total
            FROM `tabCircular 12`
            WHERE {where_sql}
            """,
            params,
            as_dict=True
        )
        return {"count": count[0].total}

    # -------------------------------
    # PAGINATION MODE
    # -------------------------------
    data = frappe.db.sql(
        f"""
        SELECT
            name, status, date_created, member, member_name
        FROM `tabCircular 12`
        WHERE {where_sql}
        ORDER BY {order_by}
        LIMIT %s OFFSET %s
        """,
        params + [limit, limit_start],
        as_dict=True
    )

    return {"data": data}

@frappe.whitelist()
def search_officers(filters: str = "[]", search: str = "", limit: int = None,
                   limit_start: int = 0, order_by: str = "o.modified DESC", status: str =""):
    # -------------------------------
    # Load filters
    # -------------------------------
    try:
        filters_list = json.loads(filters)
    except Exception:
        filters_list = []

    where_clauses = []
    params = []

    # -------------------------------
    # Process each filter (AND conditions)
    # -------------------------------
    for f in filters_list:
        if not isinstance(f, list) or len(f) != 3:
            continue

        field, condition, value = f
        condition_upper = condition.upper()

        # -------------------------------
        # FIELD → TABLE ALIAS MAPPING
        # -------------------------------
        table_alias = "o"
        column_name = field

        if field == "full_name":
            table_alias = "m"
            column_name = "full_name"

        # -------------------------------
        # Normalize date fields
        # -------------------------------
        if field.lower() in ["created"]:
            value = normalize_date(str(value))
            where_clauses.append(
                f"DATE({table_alias}.`{column_name}`) {condition} %s"
            )
            params.append(value)
            continue

        # -------------------------------
        # IN / NOT IN
        # -------------------------------
        if condition_upper in ["IN", "NOT IN"]:
            if isinstance(value, list):
                placeholders = ", ".join(["%s"] * len(value))
                where_clauses.append(
                    f"{table_alias}.`{column_name}` {condition_upper} ({placeholders})"
                )
                params.extend(value)
            else:
                where_clauses.append(
                    f"{table_alias}.`{column_name}` {condition_upper} (%s)"
                )
                params.append(value)
        else:
            where_clauses.append(
                f"{table_alias}.`{column_name}` {condition} %s"
            )
            params.append(value)

    # -------------------------------
    # OR SEARCH
    # -------------------------------
    if search:
        search_lower = str(search).lower()
        search_param = f"%{search_lower}%"
        or_parts = [
            "LOWER(o.year) LIKE %s",
            "LOWER(o.district) LIKE %s",
            "LOWER(o.lodge_no) LIKE %s",
            "LOWER(o.lodge_name) LIKE %s",
            "LOWER(o.type) LIKE %s",
            "LOWER(o.position) LIKE %s",
            "LOWER(o.`dual`) LIKE %s",
            "LOWER(m.full_name) LIKE %s",
            "LOWER(o.remarks) LIKE %s",
            "LOWER(o.status) LIKE %s",
            
        ]
        where_clauses.append("(" + " OR ".join(or_parts) + ")")
        params.extend([search_param] * len(or_parts))
    # -------------------------------
    # OR status filter
    # -------------------------------
    # -------------------------------
    # STATUS FILTER (AND)
    # -------------------------------
    if status:
        status_lower = status.lower()

        if status_lower == "posted":
            where_clauses.append("o.status = %s")
            params.append("Posted")

        if status_lower == "created":
            where_clauses.append("o.status = %s")
            params.append("created")

        if status_lower == "returned":
            where_clauses.append("o.status = %s")
            params.append("returned")
        
        if status_lower == "resubmitted":
            where_clauses.append("o.status = %s")
            params.append("resubmitted")

        elif status_lower == "unposted":
            where_clauses.append("o.status IN (%s, %s, %s)")
            params.extend(["PENDING", "DRAFT", "Unposted"])

        else:
            where_clauses.append("o.status = %s")
            params.append(status)
    # -------------------------------
    # Final WHERE SQL
    # -------------------------------
    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    # -------------------------------
    # COUNT MODE
    # -------------------------------
    if not limit:
        count = frappe.db.sql(
            f"""
            SELECT COUNT(*) AS total
            FROM `tabOfficers` o
            LEFT JOIN `tabMembers` m
                ON m.name = o.member
            WHERE {where_sql}
            """,
            params,
            as_dict=True
        )
        return {"count": count[0].total}

    # -------------------------------
    # PAGINATION MODE
    # -------------------------------
    
    data = frappe.db.sql(
        f"""
        SELECT
            o.name,
            o.year,
            o.district,
            o.lodge_no,
            o.lodge_name,
            o.type,
            o.position,
            o.`dual`,
            o.member,
            m.full_name AS member_full_name,
            m.last_name AS member_last_name,
            m.middle_name AS member_middle_name,
            m.first_name AS member_first_name,
            m.lodge AS member_lodge,
            o.remarks,
            o.status
        FROM `tabOfficers` o
        LEFT JOIN `tabMembers` m
            ON m.name = o.member
        WHERE {where_sql}
        ORDER BY {order_by}
        LIMIT %s OFFSET %s
        """,
        params + [limit, limit_start],
        as_dict=True
    )
    
    result = []
    for row in data:
        row["member"] = {
            "id": row.get("member"),
            "full_name": row.get("member_full_name"),
            "last_name": row.get("member_last_name"),
            "middle_name": row.get("member_middle_name"),
            "first_name": row.get("member_first_name"),
            "lodge_no": row.get("member_lodge")
        }
        result.append(row)

    return {"data": result}

@frappe.whitelist()
def search_minutes(filters: str = "[]", search: str = "", limit: int = None,
                   limit_start: int = 0, order_by: str = "modified asc"):
    # -------------------------------
    # Load filters
    # -------------------------------
    try:
        filters_list = json.loads(filters)
    except Exception:
        filters_list = []

    where_clauses = []
    params = []

    # -------------------------------
    # Process each filter (AND conditions)
    # -------------------------------
    for f in filters_list:
        if not isinstance(f, list) or len(f) != 3:
            continue

        field, condition, value = f
        normalized_field = field.lower().strip()
        condition_upper = condition.upper()

        # -------------------------------
        # NORMAL PARENT FILTER
        # -------------------------------

        # Normalize date fields
        if field.lower() in ["modified"]:
            value = normalize_date(str(value))
            where_clauses.append(f"DATE(`{field}`) {condition} %s")
            params.append(value)
            continue

        # IN / NOT IN
        if condition_upper in ["IN", "NOT IN"]:
            if isinstance(value, list):
                placeholders = ", ".join(["%s"] * len(value))
                where_clauses.append(f"`{field}` {condition_upper} ({placeholders})")
                params.extend(value)
            else:
                where_clauses.append(f"`{field}` {condition_upper} (%s)")
                params.append(value)
        else:
            where_clauses.append(f"`{field}` {condition} %s")
            params.append(value)

    # -------------------------------
    # OR SEARCH
    # -------------------------------
    if search:
        search_lower = str(search).lower()
        search_param = f"%{search_lower}%"
        or_parts = [
            "LOWER(name) LIKE %s",
            "LOWER(status) LIKE %s",
            "LOWER(meeting_title) LIKE %s",
            "LOWER(lodge_name) LIKE %s",
            "CAST(meeting_date AS CHAR) LIKE %s"
        ]
        where_clauses.append("(" + " OR ".join(or_parts) + ")")
        params.extend([search_param] * len(or_parts))

    # -------------------------------
    # OR status filter
    # -------------------------------
    # where_clauses.append(
    #     "(LOWER(overall_status) LIKE '%%active%%' OR LOWER(overall_status) LIKE '%%demitted%%')"
    # )

    # -------------------------------
    # Final WHERE SQL
    # -------------------------------
    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    # -------------------------------
    # COUNT MODE
    # -------------------------------
    if not limit:
        count = frappe.db.sql(
            f"""
            SELECT COUNT(*) AS total
            FROM `tabMinutes of the Meeting`
            WHERE {where_sql}
            """,
            params,
            as_dict=True
        )
        return {"count": count[0].total}

    # -------------------------------
    # PAGINATION MODE
    # -------------------------------
    data = frappe.db.sql(
        f"""
        SELECT
            name,
            lodge_number,
            lodge_name,
            meeting_date,
            meeting_title,
            meeting_type,
            district,
            venue,
            status
        FROM `tabMinutes of the Meeting`
        WHERE {where_sql}
        ORDER BY {order_by}
        LIMIT %s OFFSET %s
        """,
        params + [limit, limit_start],
        as_dict=True
    )

    if data:
        names = [r["name"] for r in data]
        placeholders = ", ".join(["%s"] * len(names))

        child_tables = {
            "mom_attendees_table": "tabMOM Attendees",
            "committee_table": "tabCommittee Report",
            "balloting_table": "tabBalloting",
            "petition_of_degrees_table": "tabPetition of Degrees",
            "resolution_and_actions_information_table": "tabResolution and Actions",
            "birthday_celebrants_table": "tabBirthday Celebrants",
            "brethren_visiting_from_other_lodges_table": "tabBrethren Visiting for Other Lodges",
            "tylers_book": "tabTylers Book",
            "past_masters_present_table": "tabPast Masters Present",
            "past_ddgms_present_table": "tabPast DDGMs and Other Dignitaries Present",
            "district_officers_present_copy": "tabDistrict Officers Present",
            "glp_communications_table": "tabGLP Communications",
            "conferral_of_degrees_table": "tabConferral of Degrees",
            "table_mzjc": "tabClosing of the Lodge",
            "history_logs_table": "tabHistory Logs",
            "miscellaneous_business_table": "tabMiscellaneous Business",
        }

        child_maps = {}

        for fieldname, table in child_tables.items():
            rows = frappe.db.sql(
                f"""
                SELECT *
                FROM `{table}`
                WHERE parent IN ({placeholders})
                ORDER BY idx
                """,
                names,
                as_dict=True
            )

            grouped = {}
            for row in rows:
                grouped.setdefault(row["parent"], []).append(row)

            child_maps[fieldname] = grouped

        for row in data:
            for fieldname in child_tables:
                row[fieldname] = child_maps[fieldname].get(row["name"], [])
   
    return {"data": data}

@frappe.whitelist()
def search_member_by_name(search):
    # Normalize the input
    normalized_search = re.sub(r"[^A-Za-z\s]", "", search).strip()
    normalized_search = re.sub(r"\s+", " ", normalized_search)

    return frappe.db.sql(
        """
        SELECT *
        FROM `tabMembers`
        WHERE
            LOWER(REGEXP_REPLACE(full_name, '[^A-Za-z ]', '')) = LOWER(%(search)s)
            OR LOWER(
                REGEXP_REPLACE(
                    CONCAT_WS(' ',
                        first_name,
                        middle_name,
                        last_name
                    ),
                    '[^A-Za-z ]',
                    ''
                )
            ) = LOWER(%(search)s)
        LIMIT 1
        """,
        {
            "search": normalized_search,
        },
        as_dict=True,
    )
# def search_member_by_name(search):
#     return frappe.db.sql(
#         """
#         SELECT *
#         FROM `tabMembers`
#         WHERE
#             LOWER(full_name) = LOWER(%(search)s)
#             OR LOWER(CONCAT_WS(' ',
#                 first_name,
#                 middle_name,
#                 last_name
#             )) = LOWER(%(search)s)
#         LIMIT 1
#         """,
#         {
#             "search": search.strip()
#         },
#         as_dict=True,
#     )
# LIKE MATCH
# def search_member_by_name(search):
#     return frappe.db.sql(
#         """
#         SELECT
#             *
#         FROM `tabMembers`
#         WHERE
#             full_name LIKE %(search)s
#             OR CONCAT_WS(' ',
#                 first_name,
#                 middle_name,
#                 last_name
#             ) LIKE %(search)s
#         ORDER BY full_name
#         LIMIT 20
#         """,
#         {
#             "search": f"%{search}%"
#         },
#         as_dict=True,
#     )


@frappe.whitelist()
def validate_id_number(id_number):
    if not id_number:
        return False

    member_exists = frappe.db.exists(
        "Members",
        {"id_number": id_number}
    )

    petitioner_exists = frappe.db.exists(
        "Petitioners",
        {"id_number": id_number}
    )

    return bool(member_exists or petitioner_exists)