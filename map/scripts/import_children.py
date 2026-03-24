from datetime import datetime

import frappe
import csv
import os

#to run:
#bench execute map.scripts.import_children.run


def normalize_date(date_str):
    if not date_str or date_str.strip() == "":
        return None
    for fmt in ("%m/%d/%Y", "%d/%m/%Y", "%m-%d-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    # if no match, return as-is (or None)
    return None


def has_data(*values):
    """Return True if any value is non-empty."""
    return any(v and str(v).strip() for v in values)

def process_csv(file_path):
    print(f"\n📄 Processing file: {file_path}")

    with open(file_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            parent_id = row.get("ID")
            if not parent_id or not str(parent_id).strip():
                continue  # Skip if no parent ID

            try:
                parent_doc = frappe.get_doc("Members", parent_id)

                # --- Masonic Timeline ---
                if has_data(row.get("Details (Masonic Timeline)"), row.get("Date (Masonic Timeline)")):
                    parent_doc.append("masonic_timeline", {
                        "details": row.get("Details (Masonic Timeline)", "").strip(),
                        "date": row.get("Date (Masonic Timeline)", "").strip(),
                        "additional_info": row.get("Additional Information (Masonic Timeline)", "").strip(),
                        "type": row.get("Type (Masonic Timeline)", "").strip()
                    })

                # --- Other Lodges ---
                if has_data(
                    row.get("Lodge Type (Other Lodges)"),
                    row.get("Lodge Number (Other Lodges)"),
                    row.get("Lodge Date (Other Lodges)"),
                    row.get("LML (Other Lodges)")
                ):
                    parent_doc.append("other_lodges", {
                        "lodge_type": row.get("Lodge Type (Other Lodges)", "").strip(),
                        "lodge_no": row.get("Lodge Number (Other Lodges)", "").strip(),
                        "lodge_date": row.get("Lodge Date (Other Lodges)", "").strip(),
                        "lml": row.get("LML (Other Lodges)", "").strip()
                    })

                # --- Affiliation ---
                if has_data(row.get("Affiliation (Affiliation)"), row.get("Date (Affiliation)")):
                    parent_doc.append("affiliation", {
                        "affiliation": row.get("Affiliation (Affiliation)", "").strip(),
                        "date": row.get("Date (Affiliation)", "").strip()
                    })
                
                  # --- Other Lodges ---
                if has_data(
                    row.get("Date (Activities)"),
                    row.get("Type (Activities)"),
                    row.get("Action (Activities)"),
                    row.get("Notes (Activities)")
                ):
                    parent_doc.append("activities", {
                        "date": normalize_date(row.get("Date (Activities)", "").strip()),
                        "type": row.get("Type (Activities)", "").strip(),
                        "action": row.get("Action (Activities)", "").strip(),
                        "notes": row.get("Notes (Activities)", "").strip()
                    })

                # --- Other Lodges ---
                if has_data(
                    row.get("Date of Payment (Payment)"),
                    row.get("OR Number (Payment)"),
                    row.get("Year (Payment)"),
                    row.get("Lodge (Payment)"),
                    row.get("Amount (Payment)"),
                    row.get("Posted (Payment)"),
                    row.get("User (Payment)")
                ):
                    parent_doc.append("payment", {
                        "date_of_payment": normalize_date(row.get("Date of Payment (Payment)", "").strip()),
                        "or_number": row.get("OR Number (Payment)", "").strip(),
                        "year": row.get("Year (Payment)", "").strip(),
                        "lodge": row.get("Lodge (Payment)", "").strip(),
                        "amount": row.get("Amount (Payment)", "").strip(),
                        "posted": row.get("Posted (Payment)", "").strip(),
                        "user": row.get("User (Payment)", "").strip()
                    })

                parent_doc.save()
                frappe.db.commit()
                print(f"✅ Updated parent {parent_id}")

            except frappe.DoesNotExistError:
                print(f"⚠️ Parent not found: {parent_id}")
            except Exception as e:
                print(f"❌ Error for {parent_id}: {e}")

def run():
    # Directory containing all your CSV files
    data_dir = frappe.get_app_path("map", "import_child")

    # List of all CSV filenames
    files = [
        # "members_split_1.csv",
        # "members_split_2.csv",
        # "members_split_3.csv",
        # "members_split_4.csv",
        # "members_split_5.csv"
        #"filtered_payments.csv"
        #"officers_import.csv"
        "cleaned_activities.csv"
    ]

    for file_name in files:
        file_path = os.path.join(data_dir, file_name)
        if os.path.exists(file_path):
            process_csv(file_path)
        else:
            print(f"⚠️ File not found: {file_path}")
