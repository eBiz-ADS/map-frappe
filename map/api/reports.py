import frappe

@frappe.whitelist()
def get_conferral(name):
    # Load Parent
    conferral_report = frappe.get_doc("Conferral Report", name)

    result = {
        "conferral_report": conferral_report.as_dict(),
        "petitioners": []
    }

    for row in conferral_report.petitioners:
        
        petitioners = frappe.get_doc("Petitioners Conferral", row.petitioners_conferral)

        print(petitioners)

        result["petitioners"].append({
            "full_name": petitioners.full_name,
            "conferral_team": petitioners.conferral_team # Level 2 child table
        })

    return result
