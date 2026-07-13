import csv
import os
import frappe


def has_data(*values):
    return any(v and str(v).strip() for v in values)


def process_csv(file_path):
    print(f"\n📄 Processing file: {file_path}")

    with open(file_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        for row in reader:
            parent_id = row.get("ID", "").strip()
            district = row.get("district", "").strip()

            if not parent_id:
                continue

            try:
                parent_doc = frappe.get_doc("Regional", parent_id)

                if has_data(district):
                    # Prevent duplicates
                    exists = any(
                        d.district == district
                        for d in parent_doc.districts
                    )

                    if not exists:
                        parent_doc.append("districts", {
                            "district": district
                        })
                        parent_doc.save(ignore_permissions=True)
                        print(f"✅ Added '{district}' to {parent_id}")
                    else:
                        print(f"⏭ Skipped duplicate '{district}' for {parent_id}")

            except frappe.DoesNotExistError:
                print(f"⚠ Parent not found: {parent_id}")

            except Exception as e:
                print(f"❌ Error importing {parent_id}: {e}")

    frappe.db.commit()


def run():
    data_dir = frappe.get_app_path("map", "import_child")

    files = [
        "ACTUAL_REGIONAL_CHILDREN_NONAME_FORIMPORT_071326.csv",
    ]

    for file_name in files:
        file_path = os.path.join(data_dir, file_name)

        if os.path.exists(file_path):
            process_csv(file_path)
        else:
            print(f"⚠ File not found: {file_path}")