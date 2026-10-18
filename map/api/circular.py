
import frappe
from dataclasses import dataclass, asdict
from typing import List, Optional
import json
from datetime import datetime, date
import calendar
from frappe.utils import now, now_datetime, add_days
from calendar import monthrange

@dataclass    
class Petitioner: 
    petitioner: str
    petitioner_name: str
    type: str
    lodge: str
    isAffiliation: bool = False
    status: Optional[str] = None
    date_completed: Optional[str] = None
    date_presented: Optional[str] = None
    name: Optional[str] = None
    residence: Optional[str] = None
    occupation: Optional[str] = None

@dataclass    
class Member: 
    member_name: str
    type: str
    lodge: str
    details: Optional[str] = None
    member: Optional[str] = None
    petitioner: Optional[str]= None
    date_completed: Optional[str] = None
    
@dataclass    
class MMR: 
    mmr: str

@dataclass    
class PCR: 
    pcr: str

@dataclass
class Circular12: 
    date_created: str
    status: str
    petitioners: List[Petitioner]
    members: List[Member]
    mmr: Optional[List[MMR]] = None
    pcr: Optional[List[PCR]] = None
    member: Optional[str] = None
    member_name: Optional[str] = None
    participant: Optional[str] = None

@frappe.whitelist()
def create_circular_12(data):

    # Frappe may pass JSON string
    if isinstance(data, str):
        data = json.loads(data)

    petition_data = Circular12(
        date_created=data.get("date_created"),
        status=data.get("status"),

        petitioners=[
            Petitioner(**p)
            for p in data.get("petitioners", [])
        ],

        members=[
            Member(**m)
            for m in data.get("members", [])
        ],

        mmr=[
            MMR(**m)
            for m in data.get("mmr", [])
        ] if data.get("mmr") else [],

        pcr=[
            PCR(**p)
            for p in data.get("pcr", [])
        ] if data.get("pcr") else [],

        member=data.get("member"),
        member_name= data.get("member_name"),
        participant= data.get("participant")

    )

    create = frappe.get_doc({
        "doctype": "Circular 12",
        "date_created": datetime.today(),
        "member": petition_data.member,
        "status": petition_data.status,

        "petitioners": [
            {
                "doctype": "Circular 12 Petitioner",
                **(
                    {"petitioner": p.petitioner}
                    if p.type == "Petition for Degrees of Masonry"
                    else {"member": p.petitioner}
                ),
                "petitioner_name": p.petitioner_name,
                "date_completed": p.date_completed,
                "date_presented": p.date_presented,
                "type": p.type,
                "lodge": p.lodge,
                **(
                    {
                        "status": "PUBLISHED"
                    }
                    if petition_data.status == "PUBLISHED"
                    else {"status": p.status}
                ),
                "petition_name": p.name,
                **(
                    {
                        "occupation": p.occupation,
                        "residence": p.residence,
                    }
                    if p.type == "Petition for Degrees of Masonry"
                    else {}
                ),
            }
            for p in petition_data.petitioners
        ],

        "members": [
            {
                "doctype": "Circular 12 Member",
                # **(
                #     {"petitioner": m.member}
                #     if m.type in ["Dropped From The Roll", "Raised"]
                #     else {"member": m.member}
                # ),
                "petitioner": m.petitioner,
                "member": m.member,
                "member_name": m.member_name,
                "date_completed": m.date_completed,
                "type": m.type,
                "lodge": m.lodge,
                "details": m.details
            }
            for m in petition_data.members
        ],

        "mmr": [
            {
                "mmr": m.mmr
            }
            for m in petition_data.mmr
        ],

        "pcr_table": [
            {
                "pcr": p.pcr
            }
            for p in petition_data.pcr
        ],

        # "cases_attached": [
        #     {
        #         "case_maagement_id":  c.name
        #     }
        #     for c in petition_data.cases
        # ]
    })

    if petition_data.status == "PUBLISHED":
        create.date_published = now_datetime()

    create.insert(ignore_permissions=True)

    #  update attached Petitions' circular 12 statuses 
    # update attached Petitions' circular 12 statuses

    updates = {
        "circular12_status": petition_data.status
    }

    for item in petition_data.petitioners:

        petition_updates = updates.copy()

        if petition_data.status == "PUBLISHED":
            petition_updates["status"] = "PUBLISHED"

            published_at = now_datetime()
            petition_updates["date_published"] = published_at

            petition_doc = frappe.get_doc(
                "Petitions",
                item.name
            )

            petition_doc.append("history_logs", {
                "participant": data.get("participant"),
                "date_completed": published_at,
                "action": "PUBLISHED"
            })

            petition_doc.save(ignore_permissions=True)

        frappe.logger().info(
            f"Updating {item.name}"
        )

        frappe.db.set_value(
            "Petitions",
            item.name,
            petition_updates
        )

    #  update attached MMRs' circular 12 statuses 
    
    update_mmr = {
        "circular12_status": petition_data.status,
    }

    for item in petition_data.mmr:

        if petition_data.status == "PUBLISHED":
            published_at = now_datetime()

            update_mmr["status"] = "Published"
            update_mmr["date_published"] = published_at

            # Add history log
            mmr_doc = frappe.get_doc(
                "Monthly Member Report",
                item.mmr
            )

            mmr_doc.append("history_logs_table", {
                "participant": data.get("participant"),
                "date_completed": published_at,
                "action": "Published"
            })

            mmr_doc.save(ignore_permissions=True)

        frappe.db.set_value(
            "Monthly Member Report",
            item.mmr,
            update_mmr
        )

    # update attached PCRs' circular 12 statuses

    update_pcr = {
        "circular12_status": petition_data.status,
    }

    for item in petition_data.pcr:

        if petition_data.status == "PUBLISHED":
            published_at = now_datetime()

            update_pcr["status"] = "Published"
            update_pcr["date_published"] = published_at

            # Add history log
            pcr_doc = frappe.get_doc(
                "Post Conferral Report",
                item.pcr
            )

            pcr_doc.append("history_logs_table", {
                "participant": data.get("participant"),
                "date_completed": published_at,
                "action": "Published"
            })

            pcr_doc.save(ignore_permissions=True)

        frappe.db.set_value(
            "Post Conferral Report",
            item.pcr,
            update_pcr
        )

    frappe.db.commit()

    return {
        "status": "success",
        "message": "Circular 12 created"
    }
    
def test_scheduler_job():
    frappe.log_error(
        title="Scheduler Test",
        message=f"Scheduler ran at {now()}"
    )

def publish_circular12_scheduler_job():
    now = now_datetime()

    # USE FOR ACTUAL PUBLISHING
    # year = now.year
    # month = now.month
    # day = now.day

    # # Get last day of month (28–31)
    # last_day = monthrange(year, month)[1]

    # # Initialize
    # start_date = None
    # end_date = None

    # # 🔹 Case 1: 10th → process 1–10
    # if day == 10:
    #     start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    #     end_date = now.replace(day=10, hour=23, minute=59, second=59, microsecond=0)

    # # 🔹 Case 2: 20th → process 11–20
    # elif day == 20:
    #     start_date = now.replace(day=11, hour=0, minute=0, second=0, microsecond=0)
    #     end_date = now.replace(day=20, hour=23, minute=59, second=59, microsecond=0)

    # # 🔹 Case 3: End of month → process 21–last day
    # elif day == last_day:
    #     start_date = now.replace(day=21, hour=0, minute=0, second=0, microsecond=0)
    #     end_date = now.replace(day=last_day, hour=23, minute=59, second=59, microsecond=0)

    # else:
    #     # Not a scheduled day → do nothing
    #     frappe.log_error(
    #         title="Scheduled Publication is working",
    #         message=f"Scheduled job is running but current date is not for pubishing yet."
    #     )
    #     frappe.logger("api", allow_site=True, file_count=50).info(f"Scheduled job is running but current date is not for pubishing yet.")

    #     return

    now = now_datetime()

    # Past 10 days until now
    start_date = add_days(now, -30).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0
    )

    end_date = now.replace(
        hour=23,
        minute=59,
        second=59,
        microsecond=0
    )

    
    docs = frappe.get_all(
        "Circular 12",
        filters={
            "creation": ["between", [start_date, end_date]],
            # "status": ["!=", "Published"]
            "status": "FOR PUBLISH"
        },
        fields=["name"]
    )

    for d in docs:
        frappe.db.set_value(
            "Your DocType",
            d.name,
            "status",
            "PUBLISHED"
        )
        

    frappe.log_error(
        title="Published Circular Documents",
        message=f"Processing from {start_date} to {end_date}"
    )
    frappe.logger("api", allow_site=True, file_count=50).info(f"Processing from {start_date} to {end_date}")


    frappe.db.commit()
    

@frappe.whitelist()
def update_circular_12(circular_12_name, data):
    """
    Example payload:

    {
        "petitioners": [...],
        "members": [...],
        "mmr": [...],
        "pcr": [...],
        "status": "Completed"
    }
    """

    # Parse JSON string if needed
    if isinstance(data, str):
        data = json.loads(data)

    # Get parent document
    doc = frappe.get_doc("Circular 12", circular_12_name)

    # These are the child-table fields in the API payload
    child_tables = {
        "petitioners",
        "members",
        "mmr",
        "pcr",
    }

    # Append new Petitioners
    for row in data.get("petitioners", []):

        cleaned_row = {
            k: v
            for k, v in row.items()
            if k != "name"
        }

        # The petition's document name comes from the
        # "name" field of the incoming petitioner
        if row.get("name"):
            cleaned_row["petition_name"] = row["name"]

        doc.append("petitioners", cleaned_row)


    # Append new Members
    for row in data.get("members", []):
        cleaned_row = {
            k: v
            for k, v in row.items()
            if k != "name"
        }

        doc.append("members", cleaned_row)


    # Append new MMR
    for row in data.get("mmr", []):
        cleaned_row = {
            k: v
            for k, v in row.items()
            if k != "name"
        }

        doc.append("mmr", cleaned_row)


    # API uses "pcr"
    # Frappe child table fieldname is "pcr_table"
    for row in data.get("pcr", []):
        cleaned_row = {
            k: v
            for k, v in row.items()
            if k != "name"
        }

        doc.append("pcr_table", cleaned_row)


    # -----------------------------------
    # Update normal Circular 12 fields
    # -----------------------------------

    for key, value in data.items():

        # Skip child tables
        if key in child_tables:
            continue

        doc.set(key, value)


    # -----------------------------------
    # Publication
    # -----------------------------------

    if data.get("status") == "PUBLISHED":
        doc.date_published = now_datetime()

        for item in doc.petitioners:
            if item.status == "FOR PUBLISH":
                item.status = "PUBLISHED"

    # Save Circular 12
    doc.save(ignore_permissions=True)

        
    circular_status = data.get("status")

    # ============================================================
    # DRAFT
    # ============================================================
    # Only update the newly attached records from the request.
    # ============================================================

    if circular_status == "DRAFT":

        # -------------------------
        # New Petitioners
        # -------------------------
        for item in data.get("petitioners", []):

            petition_name = item.get("name")

            if petition_name:
                frappe.db.set_value(
                    "Petitions",
                    petition_name,
                    "circular12_status",
                    "DRAFT"
                )

        # -------------------------
        # New MMR
        # -------------------------
        for item in data.get("mmr", []):

            mmr_name = item.get("mmr")

            if mmr_name:
                frappe.db.set_value(
                    "Monthly Member Report",
                    mmr_name,
                    "circular12_status",
                    "DRAFT"
                )

        # -------------------------
        # New PCR
        # -------------------------
        for item in data.get("pcr", []):

            pcr_name = item.get("pcr")

            if pcr_name:
                frappe.db.set_value(
                    "Post Conferral Report",
                    pcr_name,
                    "circular12_status",
                    "DRAFT"
                )

    # ============================================================
    # PUBLISHED
    # ============================================================
    # Update ALL records currently attached to Circular 12.
    # This includes existing + newly attached records.
    # ============================================================

    elif circular_status == "PUBLISHED":

        published_at = now_datetime()

        # -------------------------
        # All Petitioners
        # -------------------------
        for item in doc.petitioners:

            petition_name = item.get("petition_name")

            if not petition_name:
                continue

            petition_updates = {
                "circular12_status": "PUBLISHED"
            }

            # Publish petition if it is FOR PUBLISH
            if item.get("status") == "PUBLISHED":
                petition_updates.update({
                    "status": "PUBLISHED",
                    "date_published": published_at
                })

                petition_doc = frappe.get_doc(
                    "Petitions",
                    petition_name
                )

                petition_doc.append("history_logs", {
                    "participant": data.get("participant"),
                    "date_completed": published_at,
                    "action": "PUBLISHED"
                })

                petition_doc.save(ignore_permissions=True)

            frappe.db.set_value(
                "Petitions",
                petition_name,
                petition_updates
            )

        # -------------------------
        # All MMR
        # -------------------------
        for item in doc.mmr:

            mmr_name = item.get("mmr")

            if not mmr_name:
                continue

            mmr_updates = {
                "circular12_status": "PUBLISHED",
                "status": "Published",
                "date_published": published_at
            }

            mmr_doc = frappe.get_doc(
                "Monthly Member Report",
                mmr_name
            )

            mmr_doc.append("history_logs_table", {
                "participant": data.get("participant"),
                "date_completed": published_at,
                "action": "PUBLISHED"
            })

            mmr_doc.save(ignore_permissions=True)

            frappe.db.set_value(
                "Monthly Member Report",
                mmr_name,
                mmr_updates
            )

        # -------------------------
        # All PCR
        # -------------------------
        for item in doc.pcr_table:

            pcr_name = item.get("pcr")

            if not pcr_name:
                continue

            pcr_updates = {
                "circular12_status": "PUBLISHED",
                "status": "Published",
                "date_published": published_at
            }

            pcr_doc = frappe.get_doc(
                "Post Conferral Report",
                pcr_name
            )

            pcr_doc.append("history_logs_table", {
                "participant": data.get("participant"),
                "date_completed": published_at,
                "action": "PUBLISHED"
            })

            pcr_doc.save(ignore_permissions=True)

            frappe.db.set_value(
                "Post Conferral Report",
                pcr_name,
                pcr_updates
            )
    frappe.db.commit()

    return {
        "success": True,
        "message": "Circular 12 updated successfully"
    }


def get_date_completed_circular_pcr():
    today = date.today()

    return f"""
        EXISTS (
            SELECT 1
            FROM `tabHistory Logs` h
            WHERE h.parent = `tabPost Conferral Report`.name
            AND h.action = 'For Publish'
            AND DATE(h.date_completed) <= '{today}'
        )
    """

@frappe.whitelist()
def search_pcr_circular():
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
    
    date_condition = get_date_completed_circular_pcr()
    if date_condition:
        where_clauses.append(date_condition)
    
    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
    
    data = frappe.db.sql(
        f"""
            SELECT name
            FROM `tabPost Conferral Report` 
            WHERE {where_sql}
            """,
            as_dict=True
        )

    result= []

    for p in data:
        doc = frappe.get_doc("Post Conferral Report", p.name)

        result.append({
            "name": doc.name,
            "status": doc.status,
            "lodge_name": doc.lodge_name,
            "lodge_no": doc.lodge_no,
            "date": doc.date,
            "conferral_of_degrees_table": doc.conferral_of_degrees_table        
        })

    
    return {
        "data": result
    }