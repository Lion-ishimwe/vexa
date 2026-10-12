"""
Import the supplier price workbook ("UPDATED website Prices .xlsx") into the catalog.

    python scripts/import_price_list.py "D:/VEXA/UPDATED website Prices .xlsx" --dry-run
    python scripts/import_price_list.py "D:/VEXA/UPDATED website Prices .xlsx"

Each sheet (Schneider, Legrand, AICO, Solar Inverter, HIK, UPS) is read with the
"website prices" column. Every product gets a stable supplierKey (product code where
the sheet has one), so running this again with a newer workbook updates prices
instead of adding duplicates. New products are appended so existing SKUs never move.
Rows listed in HOLD are skipped until the owner confirms them.
Photos are not set here; see scripts/apply_image_links.py.
"""
import json
import os
import re
import sys

from openpyxl import load_workbook

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CATALOG = os.path.join(ROOT, "src", "_data", "catalog.json")

NEW_DEPARTMENTS = [
    {"slug": "electrical", "name": "Electrical & Wiring",
     "tagline": "Schneider and Legrand breakers, contactors, drives, switches, sockets and trunking.",
     "img": "/assets/img/cat/electrical.svg"},
    {"slug": "solar-power", "name": "Solar & Power",
     "tagline": "Hybrid and off-grid solar inverters, lithium batteries, online UPS and backup batteries.",
     "img": "/assets/img/cat/solar-power.svg"},
]

# Products already on the site that are the same item as a workbook row
EXISTING_MATCHES = {
    "hik:DS-3E1326P-EI/M": "hikvision-24-port-smart-managed-switch",
    "hik:DS-3E1318P-EI/M": "hikvision-16-port-smart-managed-switch",
}

# Rows not published until the owner confirms what they are (sheet, row): reason
HOLD = {
    ("Schneider Price", 23): "name unreadable ('HonJaya $oJar RPP TW')",
    ("Schneider Price", 24): "name unclear ('Easy CCg6 63A 30MA ... 400v')",
    ("Schneider Price", 59): "'TeSys COMMENTS BLOCK': which contact block?",
    ("Schneider Price", 63): "'CONTACTS BLOCK' has no code; several similar lines at different prices",
    ("Schneider Price", 64): "'CONTACTS BLOCK.' has no code",
    ("Schneider Price", 65): "'TeSys CONTACTS BLOCK' has no code",
    ("Schneider Price", 67): "'TeSys CONTACTS BLOCK' has no code",
    ("Schneider Price", 68): "'TeSys CONTACTS BLOCK' has no code",
    ("Solar Inverter", 14): "'Solar Hybrid Inventor' HH6KS at 5.3M: what does the package include?",
    ("Solar Inverter", 15): "'Solar Hybrid Inventor' with battery code H-PACK-5.1",
    ("Solar Inverter", 16): "'Solar Hybrid Inventor' HH10 KS at 5.3M: what does the package include?",
    ("Solar Inverter", 17): "'Solar Hybrid Inventor' H-PACK-5.1A (listed twice)",
    ("Solar Inverter", 18): "'Solar Hybrid Inventor' H-PACK-5.1A (listed twice)",
    ("Solar Inverter", 19): "'Solar Hybrid Inventor' E10KT-D22",
    ("Solar Inverter", 20): "'Solar Hybrid Inventor' with battery code BP48100P1-G2",
}

# Schneider names in the workbook are scanned text; readable titles, keyed by row
SCHNEIDER = {
    5: ("Easy9 Switch Disconnector 2P 100A 400V", "Breakers & Protection"),
    6: ("Altivar ATV630 Variable Speed Drive 22kW 400-480V IP21", "Motor Control & Drives"),
    7: ("Homaya Solar Hybrid Inverter 6kW", "solar:Inverters"),
    8: ("Easy9 MCB 1P 6A C 6000A 230V", "Breakers & Protection"),
    9: ("Homaya Solar Hybrid Inverter 3kW", "solar:Inverters"),
    10: ("Easy9 MCB 1P 16A C 6000A 230V", "Breakers & Protection"),
    11: ("Easy9 MCB 3P 40A C 6000A 400V", "Breakers & Protection"),
    12: ("Easy9 MCB 3P 16A C 6000A 400V", "Breakers & Protection"),
    13: ("Homaya Hybrid 850", "solar:Inverters"),
    14: ("Altivar ATV320 Compact Drive 7.5kW 3PH 380-500V", "Motor Control & Drives"),
    15: ("EasyPact CVS160F PM160D 3P3D Circuit Breaker", "Breakers & Protection"),
    16: ("TeSys Giga Contactor 185A 4P 100-250V AC/DC", "Motor Control & Drives"),
    17: ("VarPlus Logic Power Factor Controller, 6 Step Outputs", "Motor Control & Drives"),
    18: ("Easy9 Switch Disconnector 2P 63A 400V", "Breakers & Protection"),
    19: ("Easy9 MCB 1P 63A C 6000A 230V", "Breakers & Protection"),
    20: ("Homaya Solar MPPT Charge Controller 3kW", "solar:Inverters"),
    21: ("Easy9 MCB 3P 50A C 6000A 400V", "Breakers & Protection"),
    22: ("Easy9 RCCB 2P 63A 30mA AC Type 230V", "Breakers & Protection"),
    25: ("Easy9 MCB 2P 6A C 6000A 230V", "Breakers & Protection"),
    26: ("TeSys Motor Circuit Breaker Thermal Magnetic 4 to 6.3A, Rocker", "Motor Control & Drives"),
    27: ("Easy9 MCB 2P 10A C 6000A 230V", "Breakers & Protection"),
    28: ("Easy9 MCB 2P 16A C 6000A 230V", "Breakers & Protection"),
    29: ("Easy9 MCB 2P 20A C 6000A 230V", "Breakers & Protection"),
    30: ("Easy TeSys Contactor 3P 32A 1NO", "Motor Control & Drives"),
    31: ("13A 250V 2 Gang Switched Socket", "Switches & Sockets"),
    32: ("Easy9 RCBO 1P+N 10A B 6kA 30mA A Type 230V", "Breakers & Protection"),
    33: ("Easy9 RCBO 1P+N 20A B 6kA 30mA A Type 230V", "Breakers & Protection"),
    34: ("TeSys Motor Circuit Breaker Thermal Magnetic 6 to 10A, Rocker", "Motor Control & Drives"),
    35: ("Easy9 MCB 3P 6A C 6000A 400V", "Breakers & Protection"),
    36: ("Harmony XA2 Pilot Light 220V AC, Red", "Motor Control & Drives"),
    37: ("Easy TeSys Contactor 3P 40A 1NO+1NC", "Motor Control & Drives"),
    38: ("TeSys Motor Circuit Breaker Thermal Magnetic 20 to 25A, Rocker", "Motor Control & Drives"),
    39: ("3P Contactor 40A 18.5kW AC3, 24V AC Coil", "Motor Control & Drives"),
    40: ("Easy TeSys Contactor 3P 18A 1NO", "Motor Control & Drives"),
    41: ("20A 250V 3 Gang 2 Way Switch", "Switches & Sockets"),
    42: ("TeSys D Thermal Overload Relay 2.5 to 4.0A Class 10A", "Motor Control & Drives"),
    43: ("TeSys Thermal Overload Relay 4.0 to 6.0A Class 10A", "Motor Control & Drives"),
    44: ("TeSys Thermal Overload Relay 9 to 13A Class 10A", "Motor Control & Drives"),
    45: ("TeSys Motor Circuit Breaker Thermal Magnetic 9 to 14A, Rocker", "Motor Control & Drives"),
    46: ("TeSys Motor Circuit Breaker Thermal Magnetic 13 to 18A, Rocker", "Motor Control & Drives"),
    47: ("TeSys D Thermal Overload Relay 23 to 32A Class 10A", "Motor Control & Drives"),
    48: ("16AX 250V 4 Gang 2 Way Switch", "Switches & Sockets"),
    49: ("Easy TeSys Contactor 3P 65A 1NO+1NC", "Motor Control & Drives"),
    50: ("16AX 250V 2 Gang 2 Way Switch", "Switches & Sockets"),
    51: ("EasyPact TVS Thermal Overload Relay", "Motor Control & Drives"),
    52: ("TeSys D Thermal Overload Relay 16 to 24A Class 10A", "Motor Control & Drives"),
    53: ("Easy TeSys Power Motor Circuit Breaker 4 to 6.3A", "Motor Control & Drives"),
    54: ("Easy TeSys Power Motor Circuit Breaker 2.5 to 4A", "Motor Control & Drives"),
    55: ("16AX 250V 3 Gang 2 Way Switch", "Switches & Sockets"),
    56: ("TVS Thermal Overload Relay 23 to 32A", "Motor Control & Drives"),
    57: ("TeSys Motor Circuit Breaker Thermal Magnetic 1 to 1.6A, Rocker", "Motor Control & Drives"),
    58: ("32A 250V 1 Gang DP Switch with LED, White", "Switches & Sockets"),
    60: ("TeSys Motor Circuit Breaker Thermal Magnetic 0.1 to 0.16A, Rocker", "Motor Control & Drives"),
    61: ("TeSys Motor Circuit Breaker Thermal Magnetic 0.25 to 0.4A, Rocker", "Motor Control & Drives"),
    62: ("TVS Thermal Overload Relay 12 to 18A", "Motor Control & Drives"),
    66: ("10AX 250V Intermediate Switch", "Switches & Sockets"),
    69: ("TeSys 3P Contactor 9A AC3 4kW 1NO+1NC, 24V AC Coil", "Motor Control & Drives"),
    70: ("TeSys 3P Contactor 9A AC3 4kW 1NO+1NC, 415V AC Coil", "Motor Control & Drives"),
    71: ("Easy TeSys Protect Thermal Overload Relay 0.63 to 1A", "Motor Control & Drives"),
    72: ("Easy TeSys Protect Thermal Overload Relay 4 to 6A", "Motor Control & Drives"),
    73: ("TeSys Auxiliary Contact Block 2NO for TeSys D", "Motor Control & Drives"),
    74: ("Easy TeSys Contactor 3P 95A 1NO+1NC", "Motor Control & Drives"),
    75: ("Altivar ATV320 Compact Drive 2.2kW 3PH 380-500V", "Motor Control & Drives"),
    76: ("TeSys Giga Contactor 265A 4P 100-250V AC/DC", "Motor Control & Drives"),
}
# The sheet row 71 reads "0.63-3A"; Easy TeSys Protect ranges are 0.63 to 1A or 1 to 1.6A,
# so the title above is the closest real range. The original text is kept in "sourceName".

LEGRAND_WORDS = [
    (r"\bMBLACK\b", "Matt Black"), (r"\bDSILVER\b", "Dark Silver"), (r"\bWHITE\b", "White"),
    (r"\b(\d)G\b", r"\1 Gang"), (r"\b(\d)W\b", r"\1 Way"), (r"\b(\d)X1G\b", r"\1 x 1 Gang"),
    (r"\bSW\b", "Switch"), (r"\bSWTD\b", "Switched"), (r"\bSWTCD\b", "Switched"), (r"\bSKT\b", "Socket"),
    (r"\bSSO\b", "Switched Socket"), (r"\bMSTD\b", "Multistandard"), (r"\bMULTISTD\b", "Multistandard"),
    (r"\bWH\b", "White"), (r"\bAN\b", "Anthracite"), (r"\bIV\b", "Ivory"), (r"\bSFC\b", "Surface"),
    (r"\bWAT\.HEATE?\b", "Water Heater"), (r"\bHE\b", "Heater"), (r"\bSP\b", "Single Pole"), (r"\bDP\b", "Double Pole"),
    (r"\bSHUT\b", "Shuttered"), (r"\bF/B\b", "Flush"), (r"\bSQ\b", "Square"), (r"\bEXT\b", "External"),
    (r"\bINT\b", "Internal"), (r"\bANG\b", "Angle"), (r"\bSUPP\b", "Support"), (r"\bMOD\b", "Module"),
    (r"\bPROG\b", "Programme"), (r"\bSKT\+LE?D?\b", "Socket with LED"), (r"\bSKT\+L\b", "Socket with LED"),
    (r"\bLED\b", "LED"), (r"\bSCHIKO\b", "Schuko"), (r"\bADAPT\.", "Adaptor "), (r"\bTV-R-SAT\b", "TV, Radio and Satellite"),
    (r"\bCV ?(\d+)\b", r"CV\1"), (r"\bH(\d+)/(\d+)\b", r"H\1/\2"),
]


def clean_spaces(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


def no_dash(s):
    return re.sub(r"\s+[-–—]\s+", ", ", s)


def legrand_title(code, name):
    s = clean_spaces(name).upper()
    s = s.replace("SOXLOS", "50X105").replace("LOSXSO", "105X50").replace("LOOXSO", "100X50").replace("HSO", "H50")
    s = s.replace("LG ", "1G ").replace(" LG ", " 1G ")
    for a, b in (("SKT+LED", "SOCKET WITH LED"), ("SKT+LE", "SOCKET WITH LED"), ("SKT+L", "SOCKET WITH LED"),
                 ("SWITCH SKT", "SWITCHED SOCKET"), ("SSO+LED", "SWITCHED SOCKET WITH LED"), ("1G1W", "1G 1W"),
                 ("WAT.HEATE", "WATER HEATER"), ("WAT.HE", "WATER HEATER"), ("EXTER.ANGLE", "EXTERNAL ANGLE"),
                 ("CV6 ", "CV65 "), (" MOLD", " MOULD"), ("1WAY", "1W"), ("SCHIKO/FR", "SCHUKO TO FRENCH")):
        s = s.replace(a, b)
    s = re.sub(r"SWITCH SK$", "SWITCHED SOCKET", s)
    s = re.sub(r" CV6$", " CV65", s)
    for pat, rep in LEGRAND_WORDS:
        s = re.sub(pat, rep, s)
    s = s.title()
    for keep in ("BS", "AX", "DLP", "DX3", "RJ45", "UTP", "USB", "TV", "LED", "MOESBS", "CAT6", "C6A", "DLP-S", "CV65", "CV80MM", "BS3M", "2P+E", "2P+T", "2P+T", "A+C", "H35/50", "H50"):
        s = re.sub(rf"\b{re.escape(keep.title())}\b", keep, s)
    s = re.sub(r"\b(\d+)Ax\b", r"\1AX", s)
    s = re.sub(r"\b(\d+)A\b", r"\1A", s)
    s = re.sub(r"\bBs(\d+)A\b", r"BS \1A", s)
    s = re.sub(r"\bBs\b", "BS", s)
    s = re.sub(r"\bCat6\b", "Cat6", s)
    s = re.sub(r"(\d+)X(\d+)", r"\1 x \2", s)
    s = re.sub(r"(\d+)x(\d+)", r"\1 x \2", s)
    s = re.sub(r"\b(\d+) ?Mm\b", r"\1 mm", s)
    s = re.sub(r"\b(\d+)M\b", r"\1 m", s)
    for a, b in (("With Sb", "with SB"), ("With LED", "with LED"), (" Fb ", " FB "), ("Switch Socket", "Switched Socket"),
                 ("Schuko To French", "Schuko to French"), ("Radio And Satellite", "Radio and Satellite")):
        s = s.replace(a, b)
    # colour from the code family when the text does not say it
    digits = re.sub(r"\D", "", code)
    colour = ""
    if code.upper().endswith("MB"):
        colour = "Black"
    elif code.upper().endswith("MW"):
        colour = "White"
    elif digits.startswith("6177") and "Anthracite" not in s:
        colour = "Anthracite"
    elif digits.startswith("6178") and "Ivory" not in s:
        colour = "Ivory"
    title = "Legrand " + s.strip(" .")
    if colour and colour not in title:
        title += f", {colour}"
    return no_dash(clean_spaces(title))


def legrand_aisle(name):
    n = name.upper()
    if "DX3" in n:
        return "Breakers & Protection"
    if any(w in n for w in ("TRUNKING", "DLP", "GLAND", "ANGLE", "CHEEK", "PARTITION", "END TAP", "BRACKET", "FRAME", "MOSAIC", "MOESBS")):
        return "Trunking & Accessories"
    return "Switches & Sockets"


def aico_aisle(name):
    n = name.lower()
    if "patch cord" in n:
        return ("networking", "Patch Cords")
    if "patch panel" in n:
        return ("networking", "Patch Panels")
    if "wall mounted" in n or "floor type" in n or n == "fans":
        return ("networking", "Racks & Cabinets")
    if "face plate" in n or "socket" in n or "module" in n:
        return ("networking", "Faceplates & Data Sockets")
    return ("networking", "Network Cable")


def aico_title(name):
    s = clean_spaces(name).replace("Doublee", "Double")
    s = re.sub(r"(\d+)\*(\d+)mm", r"\1 x \2 mm", s)
    s = re.sub(r"(\d+)meter\b", r"\1 m", s)
    s = s.replace("RJ45 Cat R45 TO RJ45", "RJ45 to RJ45").replace("Through module", "Through Module")
    s = s.replace("Patch cord", "Patch Cord").replace("Face plate", "Face Plate")
    s = re.sub(r"(\d+)Ports", r"\1 Ports", s)
    s = re.sub(r"^Data socket RJ45 (Single|Double) data$", r"RJ45 Data Socket, \1", s)
    s = s.replace("Face Plate Single", "Face Plate, Single").replace("Face Plate Double", "Face Plate, Double")
    if s == "Fans":
        s = "Cabinet Cooling Fan"
    if "Wall Mounted" in s or "Floor Type" in s:
        s = s.replace("Wall Mounted", "Wall Mounted Network Cabinet").replace("Floor Type", "Floor Standing Network Cabinet")
    if not s.lower().startswith("aico"):
        s = "AICO " + s
    s = re.sub(r"^Aico\b", "AICO", s)
    return no_dash(s)


HIK_GROUPS = {
    "CABLE": ("networking", "Network Cable"),
    "CAMERA": ("cctv", "Cameras & Kits"),
    "SOLAR CAMERA": ("cctv", "Cameras & Kits"),
    "CAMERA&DVR KIT": ("cctv", "Cameras & Kits"),
    "SWITCH": ("networking", "Routers & Switches"),
    "WIFI ROUTER": ("networking", "Routers & Switches"),
    "NVR": ("cctv", "Recorders & Storage"),
    "SCREEN MONITORS": ("computers", "Monitors"),
    "POWER ADAPTER": ("networking", "Adapters"),
}


def hik_place(group, desc):
    g = clean_spaces(group).upper()
    if "COAXIAL" in clean_spaces(desc).upper():
        return ("cctv", "Cabling & Connectors")
    if g in HIK_GROUPS:
        return HIK_GROUPS[g]
    if g.startswith("UPS"):
        return ("solar-power", "UPS")
    return ("security", "Access Control & Alarms")


def hik_title(code, desc, group):
    parts = clean_spaces(code).split(" ")
    model = parts[0]
    lens = next((p for p in parts[1:] if re.fullmatch(r"\d+(\.\d+)?MM", p, re.I)), "")
    d = clean_spaces(desc)
    if d.upper().startswith("DS-UPS") or d.lower() == "oversea ups":
        d = "UPS"
    if model == "DS-1LH1SCAM592C":
        d = "Mini RG59 Coaxial Cable with Power Cable"
    d = d.replace("Monitor(EU)", "Monitor (EU)").replace("M1Card", "M1 RFID Card").replace("Smart hybrid light", "Smart Hybrid Light")
    d = d.replace("POE", "PoE").replace("Poe", "PoE").replace("Acusense", "AcuSense").replace("Colorful", "ColorVu")
    title = f"Hikvision {model} {d}"
    if lens:
        title += f" ({lens.lower()})"
    return no_dash(clean_spaces(title)), model


def to_price(v):
    try:
        n = int(round(float(v)))
        return n if n > 0 else None
    except (TypeError, ValueError):
        return None


def slugify(s):
    s = s.lower().replace('"', "").replace("&", " and ").replace("+", " plus ")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:90].strip("-")


def read_rows(wb):
    rows = []  # dicts with key, title, brand, model, dept, aisle, price, desc, sheet, row, sourceName
    ws = wb["Schneider Price"]
    for r in range(5, ws.max_row + 1):
        name, price = ws.cell(r, 2).value, ws.cell(r, 6).value
        if not name:
            continue
        held = HOLD.get(("Schneider Price", r))
        spec = SCHNEIDER.get(r)
        title, aisle = (spec if spec else (clean_spaces(name), "Motor Control & Drives"))
        dept = "electrical"
        if aisle.startswith("solar:"):
            dept, aisle = "solar-power", aisle.split(":", 1)[1]
        rows.append(dict(key=f"schneider:r{r}:{clean_spaces(name).lower()}", title=f"Schneider {title}", brand="Schneider Electric",
                         model="", dept=dept, aisle=aisle, price=to_price(price), desc="", sheet=ws.title, row=r,
                         sourceName=clean_spaces(name), held=held))

    ws = wb["legrand"]
    seen = {}
    for r in range(4, ws.max_row + 1):
        code, name, price = ws.cell(r, 2).value, ws.cell(r, 3).value, ws.cell(r, 7).value
        if not name:
            continue
        code = clean_spaces(code).upper().replace("LG ", "LG")
        norm = re.sub(r"^LG0*", "LG", code)
        # The same code listed twice: keep one product at the higher price (owner's rule, 13 Oct 2026)
        first = seen.get(norm)
        if first is not None:
            first["price"] = max(first["price"] or 0, to_price(price) or 0) or None
            first["sourceName"] += f" (also row {r})"
            continue
        row = dict(key=f"legrand:{norm}", title=legrand_title(code, name), brand="Legrand", model=code.replace("LG", "", 1).strip(),
                   dept="electrical", aisle=legrand_aisle(name), price=to_price(price), desc="", sheet=ws.title, row=r,
                   sourceName=clean_spaces(name), held=None)
        seen[norm] = row
        rows.append(row)

    ws = wb["AICO"]
    for r in range(5, ws.max_row + 1):
        name, price = ws.cell(r, 2).value, ws.cell(r, 6).value
        if not name:
            continue
        dept, aisle = aico_aisle(clean_spaces(name))
        rows.append(dict(key=f"aico:{clean_spaces(name).lower()}", title=aico_title(name), brand="AICO", model="",
                         dept=dept, aisle=aisle, price=to_price(price), desc="", sheet=ws.title, row=r,
                         sourceName=clean_spaces(name), held=None))

    ws = wb["Solar Inverter"]
    solar_titles = {
        5: ("Hybrid Inverter HH6KS (All in One, Residential)", "Inverters", "HH6KS"),
        6: ("Lithium Battery Pack for HH6KS", "Batteries", "HH6KS"),
        7: ("Battery to Inverter Cables for HH6KS", "Batteries", "HH6KS"),
        8: ("Hybrid Inverter HH10KS (All in One, Residential)", "Inverters", "HH10KS"),
        9: ("Lithium Battery Pack for HH10KS", "Batteries", "HH10KS"),
        10: ("Battery to Inverter Cables for HH10KS", "Batteries", "HH10KS"),
        11: ("Off Grid Inverter Knight G2 6KVA 48V", "Inverters", "Knight G2 6KVA-48V"),
        12: ("Lithium Battery 5.12kWh IP21 H-PACK-5.1", "Batteries", "H-PACK-5.1"),
        13: ("Battery to Inverter Cables for H-PACK-5.1", "Batteries", "H-PACK-5.1"),
    }
    for r in range(5, ws.max_row + 1):
        name, price = ws.cell(r, 3).value, ws.cell(r, 7).value
        if not name:
            continue
        held = HOLD.get(("Solar Inverter", r))
        t = solar_titles.get(r)
        title, aisle, model = t if t else (f"{clean_spaces(name)} {clean_spaces(ws.cell(r, 2).value)}", "Inverters", clean_spaces(ws.cell(r, 2).value))
        rows.append(dict(key=f"solar:r{r}:{clean_spaces(ws.cell(r, 2).value).lower()}:{clean_spaces(name).lower()}", title=title, brand="",
                         model=model, dept="solar-power", aisle=aisle, price=to_price(price), desc="", sheet=ws.title, row=r,
                         sourceName=clean_spaces(name), held=held))

    ws = wb["HIK"]
    for r in range(4, ws.max_row + 1):
        code, desc, group, price = ws.cell(r, 2).value, ws.cell(r, 3).value, ws.cell(r, 4).value, ws.cell(r, 8).value
        if not code:
            continue
        title, model = hik_title(code, desc, group)
        dept, aisle = hik_place(group, desc)
        rows.append(dict(key=f"hik:{model}", title=title, brand="Hikvision", model=model, dept=dept, aisle=aisle,
                         price=to_price(price), desc=clean_spaces(desc), sheet=ws.title, row=r, sourceName=clean_spaces(desc), held=None))

    ws = wb["UPS"]
    for r in range(4, ws.max_row + 1):
        kind, code, desc, price = ws.cell(r, 2).value, ws.cell(r, 3).value, ws.cell(r, 4).value, ws.cell(r, 8).value
        if not code:
            continue
        code, d = clean_spaces(code), clean_spaces(desc)
        if clean_spaces(kind).lower() == "battery":
            m = re.search(r"12V/(\d+)Ah", d)
            title = f"Lead Acid Battery 12V {m.group(1)}Ah ({code})" if m else f"Battery {code}"
            aisle = "Batteries"
        else:
            m = re.search(r"(\d+)kVA/([\d.]+)kW", d, re.I) or re.search(r"(\d+)KVA", d, re.I)
            phase = "3 Phase" if "3:3" in d else "Single Phase"
            kva = m.group(1) if m else ""
            title = f"Online UPS {kva}kVA {phase} ({code})" if kva else f"Online UPS ({code})"
            aisle = "UPS"
        desc_clean = no_dash(re.sub(r"\(witnin", "(within", d)).rstrip(";").replace(";", ",")
        rows.append(dict(key=f"ups:{code.lower()}", title=title, brand="", model=code, dept="solar-power", aisle=aisle,
                         price=to_price(price), desc=desc_clean, sheet=ws.title, row=r, sourceName=d, held=None))
    return rows


def describe(row):
    """Short plain description for products the sheet gives no description for."""
    if row["desc"]:
        d = row["desc"]
        return d if d.endswith(".") else d + "."
    t = re.sub(r"^(Schneider|Legrand|AICO|Hikvision)\s+", "", row["title"])
    return f"{t}. Supplied by VEXA in Kigali, with installation available."


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    path, dry = sys.argv[1], "--dry-run" in sys.argv
    wb = load_workbook(path, data_only=True)
    rows = read_rows(wb)
    cat = json.load(open(CATALOG, encoding="utf8"))
    for d in NEW_DEPARTMENTS:
        if not any(c["slug"] == d["slug"] for c in cat["categories"]):
            cat["categories"].append({**d, "count": 0, "aisles": []})
    by_key = {p.get("supplierKey"): p for p in cat["products"] if p.get("supplierKey")}
    by_slug = {p["slug"]: p for p in cat["products"]}
    slugs = set(by_slug)
    added, repriced, held = [], [], []
    for row in rows:
        if row["held"]:
            held.append(row)
            continue
        existing = by_key.get(row["key"]) or by_slug.get(EXISTING_MATCHES.get(row["key"], ""))
        if existing:
            existing.setdefault("supplierKey", row["key"])
            if row["model"] and not existing.get("model"):
                existing["model"] = row["model"]
            if row["price"] and row["price"] != existing.get("price"):
                repriced.append((row, existing.get("price")))
                existing["price"] = row["price"]
            continue
        slug = slugify(row["title"])
        while slug in slugs:
            slug += "-2"
        slugs.add(slug)
        product = {"slug": slug, "title": row["title"], "brand": row["brand"], "model": row["model"],
                   "category": row["dept"], "aisle": row["aisle"], "price": row["price"], "desc": describe(row),
                   "img": "", "supplierKey": row["key"]}
        cat["products"].append(product)
        by_key[row["key"]] = product
        added.append(product)
    for c in cat["categories"]:
        items = [p for p in cat["products"] if p["category"] == c["slug"]]
        c["count"] = len(items)
        c["aisles"] = list(dict.fromkeys(p["aisle"] for p in items))
    print(f"{len(added)} new, {len(repriced)} repriced, {len(held)} held; catalog now {len(cat['products'])} products")
    for row, old in repriced:
        print(f"  PRICE {row['title']}: {old or 0:,} -> {row['price']:,}")
    for row in held:
        print(f"  HELD  {row['sheet']} row {row['row']}: {row['sourceName']} ({row['held']})")
    if not dry:
        with open(CATALOG, "w", encoding="utf8") as f:
            f.write(json.dumps(cat, indent=2, ensure_ascii=False) + "\n")
    return added


if __name__ == "__main__":
    main()
