from datetime import datetime
import frappe
import csv
import os


def get_batch_log_file(batch_id):
    log_dir = frappe.get_site_path("private", "files", "import_logs")

    os.makedirs(log_dir, exist_ok=True)

    return os.path.join(
        log_dir,
        f"masonic_import_batch_{batch_id}.log.txt"
    )

LOG_FILE = frappe.get_site_path("private", "files", "masonic_service_import.log.txt")

BATCH_SIZE = 500  # adjust depending on server load

def write_log(log_file, message: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")

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
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except:
            continue

    return None


def has_data(*values):
    return any(v and str(v).strip() for v in values)


def process_masonic_service_records(file_path):
    print(f"📄 Processing: {file_path}")

    batch_updates = []
    batch_id = 1
    log_file = get_batch_log_file(batch_id)
    success_count = 0
    failed_count = 0

    with open(file_path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)

        for row_number, row in enumerate(reader, start=2):  
            # start=2 because row 1 is header
            member_id = str(row.get("ID", "")).strip()

            if not member_id:
                continue

            # ✅ DEBUG PRINT
            print(f"🔄 Processing row {row_number} | member: {member_id}")

            if has_data(
                row.get("Record Type"),
                row.get("Record Value"),
                row.get("Additional Info")
            ):

                batch_updates.append({
                    "row_number": row_number,
                    "member": member_id,
                    "record_type": row.get("Record Type", "").strip(),
                    "record_value": row.get("Record Value", "").strip(),
                    "lodge_no": row.get("Lodge No", "").strip(),
                    "lodge_name": row.get("Lodge Name", "").strip(),
                    "additional_info": row.get("Additional Info", "").strip(),
                    "date_official": normalize_date(row.get("Date Official", "")),
                    "date_circularized": normalize_date(row.get("Date Circularized", "")),
                    "date_encoded": normalize_date(row.get("Date Encoded", "")),
                    "record_encoder": row.get("Encoder", "").strip(),
                })

            # 🔥 Process batch
            if len(batch_updates) >= BATCH_SIZE:
                log_file = get_batch_log_file(batch_id)

                success, failed = flush_batch(batch_updates, log_file)

                batch_id += 1
                success_count += success
                failed_count += failed

                batch_updates = []

        # final batch
        if batch_updates:
            log_file = get_batch_log_file(batch_id)

            success, failed = flush_batch(batch_updates, log_file)
            success_count += success
            failed_count += failed

    frappe.db.commit()
    print("\n============================")
    print(f"✅ SUCCESSFULLY IMPORTED: {success_count}")
    print(f"❌ FAILED IMPORTS: {failed_count}")
    print("============================")
    print("✅ Import completed")


def flush_batch(records, log_file):
    """
    Batch append to child table
    """
    grouped = {}
    success_count = 0
    failed_count = 0

    # Group by member (important for efficiency)
    for r in records:
        grouped.setdefault(r["member"], []).append(r)

    for member, rows in grouped.items():
        try:
            doc = frappe.get_doc("Members", member)

            for r in rows:
                doc.append("masonic_service_records", {
                    "record_type": r["record_type"],
                    "record_value": r["record_value"],
                    "additional_info": r["additional_info"],
                    "lodge_no": r["lodge_no"],
                    "lodge_name": r["lodge_name"],
                    "date_official": r["date_official"],
                    "date_circularized": r["date_circularized"],
                    "date_encoded": r["date_encoded"],
                    "record_encoder": r["record_encoder"],
                })

            doc.save(ignore_permissions=True)
            success_count += len(rows)

            # ✅ SUCCESS LOG with row number
            for r in rows:
                # write_log(
                #     log_file,
                #     f"SUCCESS | row={r['row_number']} | member={member} | "
                #     f"type={r['record_type']} | info={r['additional_info']}"
                # )
                print(f"✅ Successfully added row : {r['row_number']} | member={member} ")

        except frappe.DoesNotExistError:
            print(f"⚠️ Member not found: {member}")
            # ❌ ERROR LOG with row numbers
            write_log(
                log_file,
                f"FAILED | rows={[r['row_number'] for r in rows]} | member={member} | Member does not exist"
            )

            failed_count += len(rows)

        except Exception as e:
            # ❌ ERROR LOG with row numbers
            write_log(
                log_file,
                f"FAILED | rows={[r['row_number'] for r in rows]} | member={member} | error={str(e)}"
            )

            print(f"❌ Error for {member}: {e}")
            failed_count += len(rows)

    return success_count, failed_count

def run():
    data_dir = frappe.get_app_path("map", "import_child")

    files = ["masonic_records_combined_test_import.csv"]

    for file_name in files:
        file_path = os.path.join(data_dir, file_name)

        if os.path.exists(file_path):
            process_masonic_service_records(file_path)
        else:
            print(f"⚠️ File not found: {file_path}")