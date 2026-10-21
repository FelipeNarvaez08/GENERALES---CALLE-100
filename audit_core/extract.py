from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import re
import fitz

@dataclass
class DocumentText:
    filename: str
    text: str
    page_texts: list[str]
    page_count: int
    extraction_mode: str

    def evidence(self, page_no: int, needle: str = "", window: int = 500) -> str:
        if not self.page_texts or page_no < 1 or page_no > len(self.page_texts):
            return ""
        t = self.page_texts[page_no-1]
        if needle:
            pos = t.lower().find(needle.lower())
            if pos >= 0: return f"Página {page_no}: …{t[max(0,pos-window//2):pos+window//2]}…"
        return f"Página {page_no}: {t[:window]}"

def _ocr_page(page, scale: float = 1.4) -> str:
    try:
        import pytesseract
        from PIL import Image
        pix = page.get_pixmap(matrix=fitz.Matrix(scale,scale), alpha=False)
        import io
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        return pytesseract.image_to_string(img, lang="spa+eng", config="--psm 6", timeout=30)
    except Exception:
        return ""

def extract_pdf(file_bytes: bytes, filename: str, enable_ocr: bool = False, full_ocr: bool = False) -> DocumentText:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    page_texts=[]; used_ocr=False
    for page in doc:
        base=(page.get_text("text", sort=True) or "").strip()
        # Many insurer PDFs have a selectable form layer but the schedules/tables are embedded as scans.
        # OCR those pages as a supplement so the native text and the visible table can both be inspected.
        has_images = len(page.get_images(full=True)) > 0
        # Default mode OCRs the schedule/cover pages, where insured values and deductibles usually live.
        # Full mode is available for long scanned clauses and endorsements.
        is_policy_schedule = ("POLIZA DE SEGURO" in base.upper() and "SLIP DE COTIZACION" not in base.upper()) or any(k in filename.lower() for k in ("pol_", "poliza", "póliza"))
        should_ocr = enable_ocr and ((full_ocr and (len(base) < 5000 or has_images)) or (is_policy_schedule and page.number < 3 and has_images and len(base) < 5000))
        if should_ocr:
            ocr=_ocr_page(page, scale=2.0 if page.number == 0 else 1.4)
            if len(ocr.strip()) > max(40, int(len(base.strip()) * .20)) and (page.number == 0 or len(ocr.strip()) > 100):
                base = base + "\n[OCR COMPLEMENTARIO]\n" + ocr
                used_ocr=True
        page_texts.append(base)
    text="\n\n".join(f"[PÁGINA {i+1}]\n{t}" for i,t in enumerate(page_texts))
    total=sum(len(x.strip()) for x in page_texts)
    mode="texto+OCR" if used_ocr else ("texto" if total > 80 else "requiere OCR")
    return DocumentText(filename,text,page_texts,len(doc),mode)

def normalize_space(s: str) -> str: return re.sub(r"\s+", " ", s or "").strip()
def normalize_identity(s: str) -> str:
    s=(s or "").upper().translate(str.maketrans("ÁÉÍÓÚÜÑ","AEIOUUN"))
    s=re.sub(r"\b(PH|P H|PROPIEDAD HORIZONTAL)\b"," ",s)
    return re.sub(r"[^A-Z0-9]","",s)
def normalize_nit(s: str) -> str: return re.sub(r"\D","",s or "")
def find_first(patterns: list[str], text: str, flags=re.I | re.M) -> Optional[str]:
    for pat in patterns:
        m=re.search(pat,text,flags)
        if m: return normalize_space(m.group(1))
    return None

def _money_after(label_patterns, text):
    return find_first([p + r"\s*\$?\s*([\d.,]+)" for p in label_patterns], text)

def extract_fields(doc: DocumentText, kind: str) -> dict:
    raw="\n".join(doc.page_texts); flat=normalize_space(raw)
    fields={"document":doc.filename,"document_kind":kind,"page_count":doc.page_count,"extraction_mode":doc.extraction_mode}
    if kind == "slip":
        validity=find_first([r"VIGENCIA DEL\s+SEGURO\s+(.+?)\s+1\. OBJETO DEL SEGURO"],flat)
        if not validity and "A CONVENIR" in flat.upper() and "VIGENCIA DEL" in flat.upper(): validity="Anual desde fecha a convenir"
        fields.update({
            "slip_number":find_first([r"SLIP\s+DE\s+COTIZACI[ÓO]N\s+No\s*([\w-]+)"],flat),
            "insured":find_first([r"ASEGURADO\s*:\s*(.+?)\s+NIT\s*:"],flat),
            "policyholder":find_first([r"TOMADOR\s*:\s*(.+?)\s+NIT\s*:"],flat),
            "beneficiary":find_first([r"BENEFICIARIO\s*:\s*(.+?)\s+NIT\s*:"],flat),
            "nit":find_first([r"TOMADOR\s*:\s*.+?\s+NIT\s*:\s*([\d.,-]+)"],flat),
            "city":find_first([r"CIUDAD\s*:\s*(.+?)\s+FECHA DE COTIZACIÓN"],flat),
            "address":find_first([r"UBICACIÓN DE LA COPROPIEDAD\s+(.+?)\s+AÑO DE CONSTRUCCIÓN"],flat),
            "construction_year":find_first([r"AÑO DE CONSTRUCCIÓN\s+(\d{4})"],flat),
            "property_type":find_first([r"TIPO DE COPROPIEDAD\s+(.+?)\s+SEGURO"],flat),
            "validity_text":validity,
            "quote_date":find_first([r"FECHA DE COTIZACIÓN\s+([\wáéíóúÁÉÍÓÚ.-]+)"],flat),
            "sum_insured":find_first([r"TOTAL VALOR ASEGURADO\s*\$?\s*([\d.,]+)"],flat),
            "premium":None,
            "tax":None,
            "total_payable":None,
            "premium_including_tax":find_first([r"PRIMA ANUAL INCLUIDO IVA\s*\$?\s*([\d.,]+)"],flat),
            "policy_number":None,
        })
    else:
        number_match=re.search(r"([\d]{2}-[\d]{2}-[\d]+)",flat)
        date_area=flat
        idx=flat.upper().find("FECHA DE EXPEDICION")
        if idx>=0: date_area=flat[idx:idx+1800]
        date_tokens=re.findall(r"\d{1,2}\s*/\s*\d{1,2}\s*/\s*\d{4}",date_area)
        date_tokens=[re.sub(r"\s+","",x) for x in date_tokens]
        fields.update({
            "policy_number":number_match.group(1) if number_match else None,
            "insured":find_first([r"ASEGURADO\s+(.+?)\s+NIT"],flat),
            "policyholder":find_first([r"TOMADOR\s+(.+?)\s+NIT"],flat),
            "beneficiary":find_first([r"BENEFICIARIO\s+(.+?)\s+NIT"],flat),
            "nit":find_first([r"TOMADOR\s+.+?\s+NIT\s+([\d.,-]+)"],flat),
            "city":find_first([r"CIUDAD DE EXPEDICIÓN\s+(.+?)\s+SUCURSAL"],flat),
            "address":find_first([r"DIRECCION\s+(.+?)\s+CIUDAD"],flat),
            "issue_date":date_tokens[0] if len(date_tokens)>0 else None,
            "start_date":date_tokens[1] if len(date_tokens)>1 else find_first([r"VIGENCIA SEGURO.*?DESDE LAS 24 HORAS.*?(\d{1,2}/\d{1,2}/\d{4})"],flat),
            "end_date":date_tokens[2] if len(date_tokens)>2 else None,
            "sum_insured":find_first([r"TOTAL SUMA ASEGURADA\s*:?\s*\$?\s*[\*xX#a-zA-Z]*\s*([\d][\d.,]*)",r"TOTAL SUMA ASEGURADA\s+\$?\s*[\*xX#a-zA-Z]*\s*([\d][\d.,]*)"],flat),
            "premium":find_first([r"\bPRIMA\s*:\s*\$?\s*[\*xX#a-zA-Z]*\s*([\d][\d.,]*)"],flat),
            "tax":find_first([r"\bIVA\s*:\s*\$?\s*[\*xX#a-zA-Z]*\s*([\d][\d.,]*)"],flat),
            "total_payable":find_first([r"TOTAL A PAGAR\s*:\s*\$?\s*[\*xX#a-zA-Z]*\s*([\d][\d.,]*)"],flat),
            "payment_plan":find_first([r"PLAN DE PAGO:\s*(.+?)\s+TÉRMINO PARA EL PAGO"],flat),
        })
    return fields
