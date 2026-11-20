"""Explicit name aliases between external lottery feeds and the app catalog.

Only unambiguous aliases are included. Schedule disagreements are not aliases for
schedule validation; raw provider names are retained in scraper output.
"""
import unicodedata
import re

ALIASES = {
    "anguilla 8am": "Anguila 8 AM",
    "anguilla 9am": "Angila 9 AM",
    "anguilla 10am": "Anguila 10 AM",
    "anguilla 11am": "Anguila 11 AM",
    "anguilla 12pm": "Anguila 12 PM",
    "anguilla 1pm": "Anguila 1 PM",
    "anguilla 2pm": "Anguila 2 PM",
    "anguilla 3pm": "Anguila 3 PM",
    "anguilla 4pm": "Anguila 4 PM",
    "anguilla 5pm": "Anguila 5 PM",
    "anguilla 6pm": "Anguila 6 PM",
    "anguilla 7pm": "Anguila 7 PM",
    "anguilla 8pm": "Anguila 8 PM",
    "anguilla 9pm": "Anguila 9 PM",
    "anguilla 10pm": "Anguila 10 PM",
    "haiti bolet 9:30 am": "Haití 1",
    "haiti bolet 10:30 am": "Haití 2",
    "haiti bolet 1:30 pm": "Haití 3",
    "haiti bolet 4:30 pm": "Haití 4",
    "haiti bolet 5:30 pm": "Haití 5",
    "haiti bolet 6:30 pm": "Haití 6",
    "el quemaito mayor": "Quemaito",
    "el quinielon dia": "Quinielón",
    "la primera": "Primera",
    "lotedom": "Lotedom",
    # LotteryUSA provider labels mapped to the application's catalog labels.
    # Keep the source label alongside canonical name; this does not validate schedules.
    "florida 9:45 pm": "Florida 9:50 PM",
    "new jersey 10:57 pm": "New Jersey 10:50 PM",
    "georgia 6:59 pm": "Georgia 7 PM",
    "georgia 11:34 pm": "Georgia 11:40 PM",
    "texas 10:12 pm": "Texas 11 PM",
}
def normalize_name(name):
    value=unicodedata.normalize("NFKD", str(name or ""))
    value="".join(ch for ch in value if not unicodedata.combining(ch))
    value=re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    return re.sub(r"\s+", " ", value)
def canonical_name(name):
    key=normalize_name(name)
    for alias,target in ALIASES.items():
        if normalize_name(alias)==key:
            return target
    return str(name or "").strip()
