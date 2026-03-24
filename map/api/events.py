import frappe

@frappe.whitelist()
def get_events_for_lodge(lodge_no):
    event_names = frappe.get_all(
        "Invited Lodges for Events",
        filters={"lodge_no": str(lodge_no)},
        pluck="parent"
    )

    if not event_names:
        return []

    return frappe.get_all(
        "Events",
        filters={"name": ["in", event_names]},
        fields=[
            "name",
            "event_name",
            "date_time",
            "location"
        ],
        order_by="date_time desc"
    )


@frappe.whitelist()
def get_all_events():
    return frappe.get_all(
        "Events",
        fields=[
            "name",
            "event_name",
            "venue",
            "date_time",
            "event_type"
        ],
        limit_page_length=1000
    )


@frappe.whitelist()
def get_all_district_fields():
    """
    Fetch all District records with full usable fields.
    """

    districts = frappe.get_all(
        "District",
        fields=[
            "name",
            "district",
            "location"
        ],
        limit_page_length=1000
    )

    # Normalize (optional but recommended)
    result = []
    for d in districts:
        result.append({
            "name": d.name,
            "district": d.district or d.name,
            "location": d.location
        })

    return result

