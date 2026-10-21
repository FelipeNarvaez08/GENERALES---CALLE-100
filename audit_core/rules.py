from __future__ import annotations
import re
from datetime import datetime
from .extract import normalize_identity, normalize_nit


def parse_money(value):
    if value is None: return None
    s=str(value).strip().replace(" ","")
    if not s: return None
    # Preserve whole currency units; drop explicit decimal cents in common US/Colombian formats.
    if re.search(r",\d{2}$",s) and "." in s:
        s=s.rsplit(",",1)[0].replace(".","").replace(",","")
    elif re.search(r"\.\d{2}$",s) and "," in s:
        s=s.rsplit(".",1)[0].replace(",","").replace(".","")
    else:
        s=re.sub(r"[^\d]","",s)
        return int(s) if s else None
    digits=re.sub(r"[^\d]","",s)
    return int(digits) if digits else None

def parse_date(value):
    if not value: return None
    value = str(value).strip().replace(" ", "")
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y"):
        try: return datetime.strptime(value, fmt).date()
        except ValueError: pass
    # Spanish textual date, e.g. 15-oct.-26
    months = {"ene":1,"feb":2,"mar":3,"abr":4,"may":5,"jun":6,"jul":7,"ago":8,"sep":9,"oct":10,"nov":11,"dic":12}
    m = re.search(r"(\d{1,2})[- /]([a-záéíóú]{3})\.?[- /](\d{2,4})", value, re.I)
    if m:
        day, mon, year = int(m.group(1)), m.group(2).lower()[:3], int(m.group(3))
        year = year + 2000 if year < 100 else year
        if mon in months:
            try: return datetime(year, months[mon], day).date()
            except ValueError: return None
    return None

def finding(severity, category, field, slip_value, policy_value, message, evidence=""):
    return {"Severidad":severity,"Categoría":category,"Campo":field,"Slip / cotización":slip_value or "No identificado",
            "Póliza emitida":policy_value or "No identificado","Hallazgo":message,"Evidencia / contexto":evidence,
            "Estado humano":"Pendiente","Comentario del revisor":""}

def audit_pair(slip, policy, slip_text, policy_text):
    """Dispatch to product-specific deterministic rules."""
    from .rules_copropiedades import audit_copropiedades
    return audit_copropiedades(slip, policy, slip_text, policy_text)
