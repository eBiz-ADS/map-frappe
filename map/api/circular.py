
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
    name: str
    petitioner: str
    petitioner_name: str
    type: str
    lodge: str
    status: Optional[str] = None
    date_completed: Optional[str] = None


@dataclass    
class Member: 
    member_name: str
    type: str
    lodge: str
    member: Optional[str] = None
    date_completed: Optional[str] = None
    
@dataclass    
class MMR: 
    mmr: str

@dataclass
class Petitions: 
    date_created: str
    status: str
    petitioners: List[Petitioner]
    members: List[Member]
    mmr: Optional[List[MMR]] = None
    member: Optional[str] = None

@frappe.whitelist()
def create_circular_12(data):

    # Frappe may pass JSON string
    if isinstance(data, str):
        data = json.loads(data)

    petition_data = Petitions(
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

        member=data.get("member")
    )

    create = frappe.get_doc({
        "doctype": "Circular 12",
        "date_created": datetime.today(),
        "member": petition_data.member,
        "status": petition_data.status,

        "petitioners": [
            {
                "doctype": "Circular 12 Petitioner",
                "petitioner": p.petitioner,
                "date_completed": p.date_completed,
                "type": p.type,
                "lodge": p.lodge,
                "status": p.status,
                "petitioner_name": p.petitioner_name,
                "petition_name": p.name
            }
            for p in petition_data.petitioners
        ],

        "members": [
            {
                "doctype": "Circular 12 Member",
                "member": m.member,
                "member_name": m.member_name,
                "date_completed": m.date_completed,
                "type": m.type,
                "lodge": m.lodge
            }
            for m in petition_data.members
        ],

        "mmr": [
            {
                "mmr": m.mmr
            }
            for m in petition_data.mmr
        ]
    })

    create.insert(ignore_permissions=True)

    updates = {
        "circular12_status": petition_data.status
    }

    if petition_data.status == "PUBLISHED":
        updates["status"] = "PUBLISHED"

    for item in petition_data.petitioners:
        frappe.logger().info(f"Updating {item.petitioner}")
        # frappe.logger("api", allow_site=True, file_count=50).info(f"Updating {item.petitioner}")
        frappe.db.set_value(
            "Petitions",
            item.name,
            updates
        )

    update_mmr = {
        "circular12_status": petition_data.status,
    }

    for item in petition_data.mmr:
        frappe.db.set_value(
            "Monthly Member Report",
            item.mmr,
            update_mmr
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
    start_date = add_days(now, -10).replace(
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
        "status": "Completed"
    }
    """

    # Parse JSON string if needed
    if isinstance(data, str):
        data = json.loads(data)

    # Get parent document
    doc = frappe.get_doc("Circular 12", circular_12_name)

    # Child tables you want to update
    child_tables = ["petitioners", "members", "mmr"]

    for fieldname in child_tables:
        if fieldname in data:

            # append new rows instead of overwriting
            for row in data[fieldname]:

                # remove fields that should not be inserted
                cleaned_row = {
                    k: v
                    for k, v in row.items()
                    if k != "name"
                }

                doc.append(fieldname, cleaned_row)

    # Update normal fields
    for key, value in data.items():
        if key not in child_tables:
            doc.set(key, value)

    doc.save(ignore_permissions=True)
    # -----------------------------------
    # Update linked Petition documents
    # -----------------------------------

    updates = {
        "circular12_status": data.get("status")
    }

    if data.get("status") == "PUBLISHED":
        updates["status"] = "PUBLISHED"

    # use petitioners from Circular 12 document
    for item in doc.petitioners:

        petition_name = item.get("petition_name")

        if petition_name:

            frappe.logger().info(
                f"Updating Petition {petition_name}"
            )

            frappe.db.set_value(
                "Petitions",
                petition_name,
                updates
            )
            
    updates_mmr = {
        "circular12_status": data.get("status")
    }

    if data.get("status") == "PUBLISHED":
        updates_mmr["date_published"] = datetime.today()
        updates_mmr["status"] = "Published"        
            
    # use MMR from Circular 12 document
    for item in doc.mmr:

        mmr_name = item.get("mmr")

        if mmr_name:

            frappe.logger().info(
                f"Updating Monthly Member Report{mmr_name}"
            )

            frappe.db.set_value(
                "Monthly Member Report",
                mmr_name,
                updates_mmr
            )
            
    frappe.db.commit()

    return {
        "success": True,
        "message": "Circular 12 updated successfully"
    }