import csv
import os
import frappe

from datetime import datetime
from frappe.utils import now


BATCH_SIZE = 5000


def normalize_date(date_str):
    if not date_str or not str(date_str).strip():
        return None

    date_str = str(date_str).strip()

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
            return datetime.strptime(
                date_str,
                fmt
            ).strftime("%Y-%m-%d")
        except Exception:
            pass

    return None


def get_log_file(batch_no):
    log_dir = frappe.get_site_path(
        "private",
        "files",
        "import_logs"
    )

    os.makedirs(log_dir, exist_ok=True)

    return os.path.join(
        log_dir,
        f"masonic_service_import_batch_{batch_no}.txt"
    )


def write_log(log_file, message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print("LOG ->", log_file, message)

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")
        f.flush()

        
def flush_batch(rows_to_insert, batch_no):
    if not rows_to_insert:
        return 0

    frappe.db.bulk_insert(
        "Masonic Service Records",
        fields=[
            "name",
            "creation",
            "modified",
            "owner",
            "modified_by",
            "docstatus",
            "parent",
            "parenttype",
            "parentfield",
            "record_type",
            "record_value",
            "additional_info",
            "lodge_no",
            "lodge_name",
            "date_encoded",
            "date_official",
            "record_encoder",
        ],
        values=rows_to_insert,
    )

    frappe.db.commit()

    print(
        f"✅ Batch {batch_no}: inserted {len(rows_to_insert):,} rows"
    )

    return len(rows_to_insert)


def run():
    file_path = frappe.get_app_path(
        "map",
        "import_child",
        "masonic_records_combined_test_import.csv"
    )

    print(f"📄 Processing: {file_path}")

    valid_members = set(
        frappe.get_all("Members", pluck="name")
    )

    print(
        f"✅ Loaded {len(valid_members):,} member ids"
    )

    total_rows = 0
    success_rows = 0
    failed_rows = 0

    batch_no = 1
    rows_to_insert = []

    log_file = get_log_file(batch_no)
    print(
        f"✅ Loaded lOG FILE{log_file}"
    )

    with open(
        file_path,
        newline="",
        encoding="utf-8-sig"
    ) as f:

        reader = csv.DictReader(f)

        for row_number, row in enumerate(reader, start=2):

            total_rows += 1

            member = str(
                row.get("ID", "")
            ).strip()

            if not member:
                failed_rows += 1

                write_log(
                    log_file,
                    f"FAILED row={row_number} | missing member id"
                )

                continue

            if member not in valid_members:
                failed_rows += 1

                write_log(
                    log_file,
                    f"FAILED row={row_number} | member={member} not found"
                )

                continue

            try:

                rows_to_insert.append(
                    (
                        frappe.generate_hash(),
                        now(),
                        now(),
                        "Administrator",
                        "Administrator",
                        0,

                        member,
                        "Members",
                        "masonic_service_records",

                        row.get("Record Type", "").strip(),
                        row.get("Record Value", "").strip(),
                        row.get("Additional Info", "").strip(),

                        row.get("Lodge No", "").strip(),
                        row.get("Lodge Name", "").strip(),

                        normalize_date(
                            row.get("Date Encoded")
                        ),

                        normalize_date(
                            row.get("Date Official")
                        ),

                        row.get("Encoder", "").strip(),
                    )
                )

                success_rows += 1

            except Exception as e:

                failed_rows += 1

                write_log(
                    log_file,
                    f"FAILED row={row_number} | member={member} | {str(e)}"
                )

            if len(rows_to_insert) >= BATCH_SIZE:

                flush_batch(
                    rows_to_insert,
                    batch_no
                )

                batch_no += 1
                log_file = get_log_file(batch_no)

                rows_to_insert.clear()

                print(
                    f"📊 Progress: "
                    f"{total_rows:,} processed | "
                    f"{success_rows:,} success | "
                    f"{failed_rows:,} failed"
                )

        if rows_to_insert:

            flush_batch(
                rows_to_insert,
                batch_no
            )

    print("\n======================")
    print(f"Processed : {total_rows:,}")
    print(f"Success   : {success_rows:,}")
    print(f"Failed    : {failed_rows:,}")
    print("======================")