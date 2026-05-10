from datetime import datetime
import frappe
import csv
import os


def normalize_date(date_str):
    if not date_str or not date_str.strip():
        return None

    date_str = date_str.strip()

    # ✅ Allow year-only as-is
    if date_str.isdigit() and len(date_str) == 4:
        return date_str

    formats = [
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%m/%d/%y",
        "%d/%m/%y",
        "%m-%d-%Y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except:
            continue

    print(f"⚠️ Invalid date format: {date_str}")
    return None



# def normalize_date(date_str):
#     if not date_str or date_str.strip() == "":
#         return None
#     for fmt in ("%m/%d/%Y", "%d/%m/%Y", "%m-%d-%Y", "%Y-%m-%d"):
#         try:
#             return datetime.strptime(date_str.strip(), fmt).strftime("%Y-%m-%d")
#         except ValueError:
#             continue
#     # if no match, return as-is (or None)
#     return None

def has_data(*values):
    return any(v and str(v).strip() for v in values)

def process_csv(file_path):
    print(f"\n📄 Processing file: {file_path}")

    with open(file_path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        print(reader.fieldnames)
        for row in reader:
            parent_id = str(row.get("ID", "")).strip()
            print(f"✅ Found parent ID column: {parent_id}")
            if not parent_id:
                continue

            print(f"🔍 Fetching parent ID: {parent_id}")

            try:
                parent_doc = frappe.get_doc("Members", parent_id)

                # --- Masonic Timeline ---
                if has_data(row.get("Details (Masonic Timeline)"), row.get("Date (Masonic Timeline)")):
                    parent_doc.append("masonic_timeline", {
                        "details": row.get("Details (Masonic Timeline)", "").strip(),
                        "date": normalize_date(row.get("Date (Masonic Timeline)", "")),
                        "additional_info": row.get("Additional Information (Masonic Timeline)", "").strip(),
                        "type": row.get("Type (Masonic Timeline)", "").strip()
                    })

                # --- Other Lodges ---
                if has_data(
                    row.get("Lodge Type (Other Lodges)"),
                    row.get("Lodge Number (Other Lodges)")
                ):
                    parent_doc.append("other_lodges", {
                        "lodge_type": row.get("Lodge Type (Other Lodges)", "").strip(),
                        "lodge_no": row.get("Lodge Number (Other Lodges)", "").strip(),
                        "lodge_date": normalize_date(row.get("Lodge Date (Other Lodges)", "")),
                        "lml": row.get("LML (Other Lodges)", "").strip()
                    })

                # --- Affiliation ---
                if has_data(row.get("Affiliation (Affiliation)"), row.get("Date (Affiliation)")):
                    parent_doc.append("affiliation", {
                        "affiliation": row.get("Affiliation (Affiliation)", "").strip(),
                        "date": normalize_date(row.get("Date (Affiliation)", ""))
                    })

                parent_doc.save()

            except frappe.DoesNotExistError:
                print(f"⚠️ Parent not found: {parent_id}")
            except Exception as e:
                print(f"❌ Error for {parent_id}: {e}")

        frappe.db.commit()  # ✅ commit once


def run():
    data_dir = frappe.get_app_path("map", "import_child")

    files = [
        "expanded_members 2026-04-14 1(test-batch-CHILD-TABLE-DATA).csv"
    ]

    for file_name in files:
        file_path = os.path.join(data_dir, file_name)
        if os.path.exists(file_path):
            process_csv(file_path)
        else:
            print(f"⚠️ File not found: {file_path}")
            