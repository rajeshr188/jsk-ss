"""Reviewed showroom identity, independent of CMS and financial records."""

import json
from urllib.parse import urlencode

from django.conf import settings


def showroom_details():
    # Update this reviewed identity when the physical business details change.
    # Do not derive canonical identity from request hosts or editable CMS content.
    details = {
        "name": "Jai Sri Krishna Jewellery",
        "website": "https://jaishrikrishnajewellery.com/",
        "street": "No. 155, Azad Road",
        "locality": "Thorapadi, Vellore",
        "region": "Tamil Nadu",
        "postal_code": "632001",
        "country": "India",
        "telephone": "+919489481436",
        "telephone_display": "+91 94894 81436",
        "email": "admin@jaishrikrishnajewellery.com",
        "hours": (
            {
                "label": "Monday–Saturday",
                "display": "9:00 AM–9:00 PM",
                "days": (
                    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday",
                ),
                "opens": "09:00",
                "closes": "21:00",
            },
            {
                "label": "Sunday",
                "display": "9:00 AM–1:00 PM",
                "days": ("Sunday",),
                "opens": "09:00",
                "closes": "13:00",
            },
        ),
        "google_profile_url": settings.GOOGLE_BUSINESS_PROFILE_URL,
    }
    details["full_address"] = ", ".join(
        (
            details["street"],
            details["locality"],
            f'{details["region"]} {details["postal_code"]}',
            details["country"],
        )
    )
    # Maps URLs need no API key. Use the published address, not an invented Place ID.
    details["directions_url"] = "https://www.google.com/maps/dir/?" + urlencode(
        {"api": "1", "destination": f'{details["name"]}, {details["full_address"]}'}
    )
    return details


def showroom_structured_data():
    details = showroom_details()
    data = {
        "@context": "https://schema.org",
        "@type": "JewelryStore",
        "@id": details["website"] + "#showroom",
        "name": details["name"],
        "url": details["website"],
        "telephone": details["telephone"],
        "email": details["email"],
        "address": {
            "@type": "PostalAddress",
            "streetAddress": details["street"],
            "addressLocality": details["locality"],
            "addressRegion": details["region"],
            "postalCode": details["postal_code"],
            "addressCountry": "IN",
        },
        "openingHoursSpecification": [
            {
                "@type": "OpeningHoursSpecification",
                "dayOfWeek": [f"https://schema.org/{day}" for day in hours["days"]],
                "opens": hours["opens"],
                "closes": hours["closes"],
            }
            for hours in details["hours"]
        ],
    }
    if details["google_profile_url"]:
        data["sameAs"] = [details["google_profile_url"]]
        data["hasMap"] = details["google_profile_url"]
    # JSON-LD is data, but it still lives in an HTML script element. Prevent a
    # future business field containing HTML from terminating that element.
    return json.dumps(data, ensure_ascii=True).translate(
        {ord("<"): "\\u003C", ord(">"): "\\u003E", ord("&"): "\\u0026"}
    )
