
import frappe
from dataclasses import dataclass, asdict
from typing import List, Optional
import json
from datetime import datetime, date
import calendar
from frappe.utils import now, now_datetime
from calendar import monthrange

@dataclass    
class Petitioner: 
    petitioner: str
    type: str
    lodge: str
    status: Optional[str] = None
    date_completed: Optional[str] = None


@dataclass    
class Member: 
    member: str
    type: str
    lodge: str    
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
def create_circular_12(data: Petitions): 
    create =  frappe.get_doc({
        "doctype": "Circular 12", 
        "date_created": datetime.today(), 
        "member": data.member,
        "status": data.status,

        "petitioners": [
            {"doctype": "Circular 12 Petitioner", "petitioner": p.petitioner, "date_completed": p.date_completed, "type": p.type, "lodge": p.lodge, "status": p.status} 
            for p in data.petitioners
        ],
        "members": [
            {"doctype": "Circular 12 Member", "member": m.member, "date_completed": m.date_completed, "type": m.type, "lodge": m.lodge } 
            for m in data.members
        ],
        "mmr": [
            {"mmr": m.mmr}
            for m in data.mmr
        ]
    })

    updates = {
        "status": data.status
    }

    update_mmr = {
        "date_published":  datetime.today()
    }

    # if(data.status == "PUBLISHED"):
    for item in data.petitioners:
        frappe.db.set_value("Petitions", item.petitioner, updates)   

    create.insert()
    for item in data.mmr:
        frappe.db.set_value("Monthly Member Report", item.mmr, update_mmr)

    frappe.db.commit()

    return {
        "status": "success",
        "message": "Circular 12 created",
    }
    

def test_scheduler_job():
    frappe.log_error(
        title="Scheduler Test",
        message=f"Scheduler ran at {now()}"
    )

def publish_circular12_scheduler_job():
    now = now_datetime()

    year = now.year
    month = now.month
    day = now.day

    # Get last day of month (28–31)
    last_day = monthrange(year, month)[1]

    # Initialize
    start_date = None
    end_date = None

    # 🔹 Case 1: 10th → process 1–10
    if day == 10:
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_date = now.replace(day=10, hour=23, minute=59, second=59, microsecond=0)

    # 🔹 Case 2: 20th → process 11–20
    elif day == 20:
        start_date = now.replace(day=11, hour=0, minute=0, second=0, microsecond=0)
        end_date = now.replace(day=20, hour=23, minute=59, second=59, microsecond=0)

    # 🔹 Case 3: End of month → process 21–last day
    elif day == last_day:
        start_date = now.replace(day=21, hour=0, minute=0, second=0, microsecond=0)
        end_date = now.replace(day=last_day, hour=23, minute=59, second=59, microsecond=0)

    else:
        # Not a scheduled day → do nothing
        return

    
    docs = frappe.get_all(
        "Circular 12",
        filters={
            "creation": ["between", [start_date, end_date]],
            "status": ["!=", "Published"]
        },
        fields=["name"]
    )

    for d in docs:
        frappe.db.set_value(
            "Your DocType",
            d.name,
            "status",
            "Processed"
        )
    
    frappe.logger().info(f"Processing from {start_date} to {end_date}")

    frappe.db.commit()