import frappe
from dataclasses import dataclass, asdict
from typing import List, Optional
import json
from datetime import datetime, date
import calendar

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
    


