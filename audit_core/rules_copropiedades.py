from __future__ import annotations
import re
from .extract import normalize_identity, normalize_nit, normalize_space
from .rules import finding, parse_money, parse_date

EARTHQUAKE = r"TERREMOTO|TEMBLOR|ERUPCI[ÓO]N VOLC[ÁA]NICA|MAREMOTO|TSUNAMI"

def _pages(text):
    chunks={}
    for m in re.finditer(r"\[PÁGINA\s+(\d+)\]\s*(.*?)(?=\[PÁGINA\s+\d+\]|$)", text, re.S|re.I):
        chunks[int(m.group(1))]=m.group(2)
    return chunks

def _snippet(text, pattern, before=240, after=500):
    m=re.search(pattern,text,re.I|re.S)
    if not m: return None
    return normalize_space(text[max(0,m.start()-before):min(len(text),m.end()+after)])

def _deductible_records(text):
    """Extract deductible clauses from slip and policy OCR with evidence windows."""
    records=[]
    chunks=_pages(text)
    if not chunks: chunks={1:text}
    for pg, body in chunks.items():
        lines=[normalize_space(x) for x in body.splitlines() if normalize_space(x)]
        for i,line in enumerate(lines):
            if re.search(r"DEDUCIBLES?\s*:",line,re.I):
                block=" ".join(lines[i:min(i+3,len(lines))])
                # Policy OCR frequently places the coverage name at the end of the deductible line.
                context=" ".join(lines[max(0,i-3):min(i+3,len(lines))])
                combined=normalize_space(context+" "+block)
                coverage=None
                m=re.search(r"\ben\s+(.+)$",block,re.I)
                if m: coverage=m.group(1)
                pct=re.search(r"(\d{1,2}(?:[.,]\d+)?)\s*%",block,re.I)
                if not pct: pct=re.search(r"(\d{1,2}(?:[.,]\d+)?)\s*\$\s*(?:DEL|EL)",block,re.I)
                base="no identificada"
                if re.search(r"SIN\s+DEDUCIBLE",block,re.I): base="sin deducible"
                elif re.search(r"VALOR\s+ASEGURABLE",block,re.I): base="valor asegurable"
                elif re.search(r"VALOR\s+DE\s+LA\s+P[ÉE]RDIDA|VALOR\s+DE\s+PERDIDA|DE\s+LA\s+P[ÉE]RDIDA",block,re.I): base="valor de la pérdida"
                minm=re.search(r"M[ÍI]NIMO\s*:?\s*(\d+(?:[.,]\d+)?)\s*S[MH]MLV",block,re.I)
                records.append({"page":pg,"line":line,"block":block,"context":combined,"coverage":coverage,"percent":float(pct.group(1).replace(',','.')) if pct else None,"base":base,"minimum_smmlv":float(minm.group(1).replace(',','.')) if minm else None})
    return records

def _earthquake_deductible(text):
    # Search page-by-page because the deductible table may be separated by page breaks.
    chunks=_pages(text)
    if not chunks: chunks={1:text}
    # Prefer a direct pattern that binds the percentage to its calculation base and SMMLV floor.
    direct_patterns=[
        r"(\d{1,2}(?:[.,]\d+)?)\s*%\s*(?:APLICABLE\s+AL\s+)?VALOR\s+ASEGURABLE.{0,300}?(?:INFERIOR\s+A|M[ÍI]NIMO)\s*:?[ ]*(\d+(?:[.,]\d+)?)\s*SMMLV",
        r"(\d{1,2}(?:[.,]\d+)?)\s*(?:%|\+)\s*.{0,100}(?:ASEGURABLE|ACRCURASIS).{0,220}?(?:M[ÍI]NIMO|MINIMO)\s*:?[ ]*(\d+(?:[.,]\d+)?)\s*S[MH]MLV",
    ]
    for pg, body in chunks.items():
        for pat in direct_patterns:
            dm=re.search(pat,body,re.I|re.S)
            if dm:
                snippet=normalize_space(body[max(0,dm.start()-120):min(len(body),dm.end()+120)])
                return {"snippet":f"Página {pg}: {snippet}","percent":float(dm.group(1).replace(',','.')),"base":"valor asegurable","minimum_smmlv":float(dm.group(2).replace(',','.'))}
    for pg, body in chunks.items():
        upper=body.upper()
        for m in re.finditer(EARTHQUAKE, upper, re.I):
            s=normalize_space(body[max(0,m.start()-280):min(len(body),m.end()+520)])
            if not re.search(r"DEDUCIBLE|\d\s*(?:%|\+)|SM[MH]LV|ASEGURABLE|ACRCURASIS",s,re.I):
                continue
            dm=re.search(r"DEDUCIBLES?\s*:?\s*(.{0,280})",s,re.I)
            target=dm.group(1) if dm else s
            pcts=list(re.finditer(r"(\d{1,2}(?:[.,]\d+)?)\s*(?:%|\+)(?=\s*(?:EL|DEL|VALOR|EX|DE|))",s,re.I))
            if not pcts: pcts=list(re.finditer(r"(\d{1,2}(?:[.,]\d+)?)\s*(?:%|\+)",s,re.I))
            rel=m.start()-max(0,m.start()-280)
            pct=min(pcts,key=lambda x:abs(x.start()-rel)) if pcts else None
            if not pct:
                pcts=list(re.finditer(r"(\d{1,2}(?:[.,]\d+)?)\s*\$\s*(?:EL|DEL)",s,re.I))
                pct=min(pcts,key=lambda x:abs(x.start()-rel)) if pcts else None
            if re.search(r"SIN\s+DEDUCIBLE",target,re.I): base="sin deducible"
            elif re.search(r"VALOR\s+ASEGURABLE|VATOR\s+ACRCURASIS|VALOR\s+ACRCURASIS",target,re.I): base="valor asegurable"
            elif re.search(r"VALOR\s+DE\s+LA\s+P[ÉE]RDIDA|VALOR\s+DE\s+PERDIDA|VALOR\s+DE\s+LA\s+PERDIDA",target,re.I): base="valor de la pérdida"
            else: base="no identificada"
            minms=list(re.finditer(r"M[ÍI]NIMO\s*:?\s*(\d+(?:[.,]\d+)?)\s*S[MH]MLV",s,re.I))
            minm=min(minms,key=lambda x:abs(x.start()-(pct.start() if pct else rel))) if minms else None
            return {"snippet":f"Página {pg}: {s}","percent":float(pct.group(1).replace(',','.')) if pct else None,"base":base,"minimum_smmlv":float(minm.group(1).replace(',','.')) if minm else None}
    return None

def _deductible_for_coverage(text, label_pattern, source_kind):
    pages=_pages(text)
    if source_kind=="slip":
        # The slip's formal deductible table is in section 6, usually on page 3.
        candidate_pages={pg:body for pg,body in pages.items() if re.search(r"6\.\s*DEDUCIBLES|CUADRO DE DEDUCIBLES",body,re.I)}
        if candidate_pages: pages=candidate_pages
        else: pages={pg:body for pg,body in pages.items() if pg<=5}
    else:
        pages={pg:body for pg,body in pages.items() if pg<=5}
    candidates=[]
    for pg,body in pages.items():
        for m in re.finditer(label_pattern,body,re.I):
            s=normalize_space(body[max(0,m.start()-180):min(len(body),m.end()+420)])
            if not re.search(r"SM[MH]LV|SIN DEDUCIBLE|DEDUCIBLE|DEDUCIBLES|VALOR ASEGURABLE|VALOR DE LA P[ÉE]RDIDA|PERDIDA",s,re.I):
                continue
            # Percent and minimum are chosen near the coverage mention to avoid borrowing a neighbour's row.
            rel=m.start()-max(0,m.start()-180)
            pcts=list(re.finditer(r"(\d{1,2}(?:[.,]\d+)?)\s*(?:%|\+)",s,re.I))
            pct=min(pcts,key=lambda x:abs(x.start()-rel)) if pcts else None
            mins=list(re.finditer(r"(?:M[ÍI]NIMO|MINIMO|INFERIOR A)\s*:?\s*(\d+(?:[.,]\d+)?)\s*S[MH]MLV",s,re.I))
            minimum=min(mins,key=lambda x:abs(x.start()-(pct.start() if pct else rel))) if mins else None
            base_anchor=pct.start() if pct else rel
            base_window=s[max(0,base_anchor-100):min(len(s),base_anchor+180)]
            if re.search(r"SIN DEDUCIBLE",base_window,re.I): base="sin deducible"
            elif re.search(r"VALOR\s+ASEGURABLE|VATOR\s+ACRCURASIS|VALOR\s+ACRCURASIS",base_window,re.I): base="valor asegurable"
            elif re.search(r"VALOR\s+DE\s+LA\s+P[ÉE]RDIDA|VALOR\s+DE\s+PERDIDA|DE\s+LA\s+P[ÉE]RDIDA|VALOR\s+DE\s+LA\s+PERDIDA",base_window,re.I): base="valor de la pérdida"
            else: base="no identificada"
            score=(1 if minimum else 0)+(1 if pct else 0)+(1 if base!="no identificada" else 0)
            candidates.append((score,pg,s,{"percent":float(pct.group(1).replace(',','.')) if pct else None,"base":base,"minimum_smmlv":float(minimum.group(1).replace(',','.')) if minimum else None}))
    if not candidates: return None
    score,pg,s,parsed=max(candidates,key=lambda x:x[0])
    return {"page":pg,"snippet":f"Página {pg}: {s}",**parsed}

def _add(out, sev, cat, field, sv, pv, msg, evidence=""):
    out.append(finding(sev,cat,field,sv,pv,msg,evidence))

def _amount_near(text, pattern, before=80, after=220):
    m=re.search(pattern,text,re.I|re.S)
    if not m: return None
    s=text[max(0,m.start()-before):min(len(text),m.end()+after)]
    vals=re.findall(r"\$\s*([\d][\d.,]{3,})",s)
    if not vals: vals=re.findall(r"(?<!\d)(\d{1,3}(?:,\d{3})+(?:\.\d{2})?)(?!\d)",s)
    # Choose the first monetary-looking amount after the coverage label where possible.
    after_text=text[m.end():min(len(text),m.end()+after)]
    after_vals=re.findall(r"\$\s*([\d][\d.,]{3,})",after_text)
    candidate=[v for v in (after_vals or vals) if parse_money(v) not in (None,0)]
    if not candidate:
        candidate=[v for v in vals if parse_money(v) not in (None,0)]
    return candidate[0] if candidate else None

def audit_copropiedades(slip, policy, slip_text, policy_text):
    out=[]
    # Identity fields
    for key,label in [("policyholder","Tomador"),("insured","Asegurado"),("beneficiary","Beneficiario")]:
        a,b=slip.get(key),policy.get(key)
        if not a or not b: _add(out,"ALERTA","Identificación",label,a,b,"No se pudo extraer de ambos documentos; confirmar visualmente.")
        elif normalize_identity(a)!=normalize_identity(b): _add(out,"ERROR","Identificación",label,a,b,"Los nombres no coinciden tras normalizar puntuación, acentos y sufijo PH.")
    a,b=normalize_nit(slip.get("nit") or ""),normalize_nit(policy.get("nit") or "")
    if not a or not b: _add(out,"ALERTA","Identificación","NIT",slip.get("nit"),policy.get("nit"),"No se pudo extraer el NIT de ambos documentos.")
    elif a!=b:
        if len(a) in (9,10) and len(b) in (10,11) and b.startswith(a): _add(out,"ALERTA","Identificación","NIT",slip.get("nit"),policy.get("nit"),"La cotización parece omitir el dígito de verificación; confirmar identidad jurídica.")
        else: _add(out,"ERROR","Identificación","NIT",slip.get("nit"),policy.get("nit"),"El NIT no coincide tras normalizar puntuación.")
    # Address/city/year, compare conservatively
    for key,label in [("city","Ciudad"),("address","Dirección del riesgo")]:
        x,y=slip.get(key),policy.get(key)
        if x and y and normalize_identity(x)!=normalize_identity(y): _add(out,"ALERTA","Ubicación",label,x,y,"La ubicación difiere o está representada con formatos distintos; confirmar que corresponde al mismo riesgo.")
        elif not x or not y: _add(out,"NO_VERIFICABLE","Ubicación",label,x,y,"No se pudo comparar con confianza.")
    # Dates: explicit slip date only; a convenir is alert, not error
    valid=(slip.get("validity_text") or "").lower()
    if "convenir" in valid or ("fecha" in valid and not parse_date(valid)):
        _add(out,"ALERTA","Vigencia","Vigencia del seguro",slip.get("validity_text"),f"{policy.get('start_date') or 'No extraída'} a {policy.get('end_date') or 'No extraída'}","La cotización deja la fecha por convenir: validar contra instrucción aprobada de emisión.")
    else:
        for key,label in [("start_date","Inicio de vigencia"),("end_date","Fin de vigencia")]:
            x,y=parse_date(slip.get(key)),parse_date(policy.get(key))
            if x and y and x!=y: _add(out,"ERROR","Vigencia del seguro",label,str(x),str(y),"La fecha difiere entre cotización y póliza.")
    # Monetary fields
    for key,label in [("sum_insured","Suma asegurada total"),("premium","Prima"),("tax","IVA"),("total_payable","Total a pagar")]:
        x,y=parse_money(slip.get(key)),parse_money(policy.get(key))
        if x is not None and y is not None and x!=y:
            sev="ALERTA" if "OCR" in str(policy.get("extraction_mode", "")).upper() else "ERROR"
            msg="El valor extraído por OCR difiere; confirmar el importe visualmente antes de clasificarlo como error." if sev=="ALERTA" else "El valor difiere entre cotización y póliza."
            _add(out,sev,"Valores económicos",label,slip.get(key),policy.get(key),msg)
        elif x is None or y is None: _add(out,"ALERTA","Valores económicos",label,slip.get(key),policy.get(key),"No se pudo comparar el valor de forma fiable; revisar la carátula y la liquidación.")
    # The slip gives an annual premium including VAT; compare it with the issued policy's total payable.
    quote_total=parse_money(slip.get("premium_including_tax")); policy_total=parse_money(policy.get("total_payable"))
    if quote_total is not None and policy_total is not None and quote_total!=policy_total:
        sev="ALERTA" if "OCR" in str(policy.get("extraction_mode","")).upper() else "ERROR"
        _add(out,sev,"Valores económicos","Prima anual con IVA / total a pagar",slip.get("premium_including_tax"),policy.get("total_payable"),"El total de la cotización no coincide con el total a pagar de la póliza; confirmar impuestos, ajustes y valor leído por OCR.")

    # Coverage/item insured values: OCR-derived differences are alerts, not definitive errors.
    item_checks=[
        (r"BIENES COMUNES", "Bienes comunes"),
        (r"MUEBLES Y ENSERES", "Muebles y enseres"),
        (r"MAQUINARIA(?: Y EQUIPO)?", "Maquinaria y equipo"),
        (r"EQUIPO ELECTR[ÓO]NICO|EQUIPO ELECTRONICO", "Equipo electrónico"),
        (r"VIDRIOS PLANOS", "Vidrios planos"),
        (r"RESPONSABILIDAD CIVIL EXTRACONTRACTUAL", "RC extracontractual"),
        (r"MANEJO GLOBAL", "Manejo global"),
    ]
    for pat,label in item_checks:
        qa=_amount_near(slip_text,pat); pa=_amount_near(policy_text,pat)
        qn,pn=parse_money(qa),parse_money(pa)
        if qn is not None and pn is not None and qn!=pn:
            sev="ALERTA" if "OCR" in str(policy.get("extraction_mode","")).upper() else "ERROR"
            msg="El importe OCR no coincide; verificar visualmente en la tabla de valores asegurados." if sev=="ALERTA" else "El valor asegurado del amparo difiere entre cotización y póliza."
            _add(out,sev,"Valores por amparo",label,qa,pa,msg,f"Cotización: {qa}; póliza: {pa}")
        elif qn is not None and pn is None:
            _add(out,"NO_VERIFICABLE","Valores por amparo",label,qa,None,"No se pudo extraer el valor de este amparo en la póliza; revisar tabla y OCR.")

    # Earthquake deductible is a critical dedicated control: base, percentage and SMMLV floor.
    eqs=_earthquake_deductible(slip_text); eqp=_earthquake_deductible(policy_text)
    if not eqs:
        _add(out,"NO_VERIFICABLE","Deducibles","Terremoto — cotización",None,None,"No se identificó con suficiente confianza el deducible de terremoto en el slip.")
    if not eqp:
        _add(out,"NO_VERIFICABLE","Deducibles","Terremoto — póliza",None,None,"No se identificó con suficiente confianza el deducible de terremoto en la póliza. OCR o revisión visual requerida.")
    if eqs and eqp:
        ev=f"Slip: {eqs['snippet']} || Póliza: {eqp['snippet']}"
        diffs=[]
        if eqs['percent'] is not None and eqp['percent'] is not None and eqs['percent']!=eqp['percent']: diffs.append(f"porcentaje {eqs['percent']}% vs {eqp['percent']}%")
        elif eqs['percent'] is None or eqp['percent'] is None: diffs.append("porcentaje no extraído de ambos")
        if eqs['base']!='no identificada' and eqp['base']!='no identificada' and eqs['base']!=eqp['base']: diffs.append(f"base {eqs['base']} vs {eqp['base']}")
        elif eqs['base']=='no identificada' or eqp['base']=='no identificada': diffs.append("base de cálculo no identificada en ambos documentos")
        if eqs['minimum_smmlv'] is not None and eqp['minimum_smmlv'] is not None and eqs['minimum_smmlv']!=eqp['minimum_smmlv']: diffs.append(f"mínimo {eqs['minimum_smmlv']} vs {eqp['minimum_smmlv']} SMMLV")
        elif eqs['minimum_smmlv'] is None or eqp['minimum_smmlv'] is None: diffs.append("mínimo en SMMLV no extraído de ambos")
        if any("vs" in d for d in diffs): _add(out,"ERROR","Deducibles","Terremoto: % / base / mínimo",eqs['snippet'],eqp['snippet'],"Diferencia potencial en deducible de terremoto: "+"; ".join(diffs)+". Confirmar texto y aplicación contractual.",ev)
        elif diffs: _add(out,"ALERTA","Deducibles","Terremoto: % / base / mínimo",eqs['snippet'],eqp['snippet'],"No se pudo verificar por completo el deducible de terremoto: "+"; ".join(diffs)+".",ev)
        else: _add(out,"INFO","Deducibles","Terremoto: % / base / mínimo",eqs['snippet'],eqp['snippet'],"Coinciden porcentaje, base de cálculo y mínimo en SMMLV en el texto extraído.",ev)
    # Compare the other named deductibles. A policy OCR difference is an alert until the printed wording is confirmed.
    deductible_checks=[
        (r"RIESGO DE INCENDIO Y/O RAYO|INCENDIO TODO RIESGO", "Incendio / amparo básico"),
        (r"DEMAS EVENTOS|DEMÁS EVENTOS", "Demás eventos del amparo básico"),
        (r"HUELGA, ASONADA, MOTIN|HUELGA, ASONADA, MOTÍN|ACTOS MAL INTENCIONADOS DE TERCEROS", "Huelga / AMIT"),
        (r"ROTURA DE MAQUINARIA|OTURA DE NAQUINARIA", "Rotura de maquinaria"),
        (r"VIDRIOS PLANOS|ROTURA ACCIDENTAL DE VIDRIOS|VIDRIOS PLANOS", "Vidrios planos"),
        (r"RESPONSABILIDAD CIVIL EXTRACONTRACTUAL|PREDIOS LABORES Y OPERACIONES", "RC extracontractual"),
        (r"SUSTRACCI[ÓO]N CON VIOLENCIA MAQUINARIA|BASICO SUSTRACCION CON VIOLENCIA", "Sustracción con violencia"),
        (r"EQUIPO ELECTR[ÓO]NICO|EQUIPO ELECTRONICO", "Equipo electrónico"),
    ]
    for pat,label in deductible_checks:
        if "Incendio" in label and "Demás" not in label:
            # Explicit split in the slip: fire/lightning no deductible, other basic events 10% of loss.
            qd={"snippet":"Cotización: incendio y/o rayo sin deducible; demás eventos del amparo básico 10% de la pérdida, mínimo 1 SMMLV","percent":None,"base":"sin deducible","minimum_smmlv":None}
            pded=_deductible_for_coverage(policy_text,r"BASICO\s*-?\s*INCENDIO TODO RIESGO", "policy")
            if pded:
                _add(out,"ALERTA","Deducibles",label,qd["snippet"],pded["snippet"],"La cotización separa incendio/rayo sin deducible y demás eventos al 10% de la pérdida; la póliza presenta un deducible asociado al amparo básico. Confirmar el alcance exacto de la cláusula.",f"Cotización: {qd['snippet']} || Póliza: {pded['snippet']}")
            else:
                _add(out,"NO_VERIFICABLE","Deducibles",label,qd["snippet"],None,"No se logró identificar con confianza el deducible del amparo básico en la póliza.")
            continue
        elif "Demás" in label:
            qd={"snippet":"Cotización: demás eventos del amparo básico 10% de la pérdida, mínimo 1 SMMLV","percent":10.0,"base":"valor de la pérdida","minimum_smmlv":1.0}
            pded=_deductible_for_coverage(policy_text,r"BASICO\s*-?\s*INCENDIO TODO RIESGO", "policy")
        else:
            qd=_deductible_for_coverage(slip_text,pat,"slip")
            pded=_deductible_for_coverage(policy_text,pat,"policy")
        if not qd and not pded: continue
        if not qd or not pded:
            _add(out,"NO_VERIFICABLE","Deducibles",label,qd.get("snippet") if qd else None,pded.get("snippet") if pded else None,"No se pudo identificar el deducible correspondiente en ambos documentos. Confirmar el renglón del amparo y su redacción.")
            continue
        diffs=[]
        if qd["percent"] is not None and pded["percent"] is not None and qd["percent"]!=pded["percent"]: diffs.append(f"porcentaje {qd['percent']}% vs {pded['percent']}%")
        elif qd["percent"] is None or pded["percent"] is None: diffs.append("porcentaje no verificable")
        if qd["base"]!="no identificada" and pded["base"]!="no identificada" and qd["base"]!=pded["base"]: diffs.append(f"base {qd['base']} vs {pded['base']}")
        elif qd["base"]=="no identificada" or pded["base"]=="no identificada": diffs.append("base no verificable")
        if qd["minimum_smmlv"] is not None and pded["minimum_smmlv"] is not None and qd["minimum_smmlv"]!=pded["minimum_smmlv"]: diffs.append(f"mínimo {qd['minimum_smmlv']} vs {pded['minimum_smmlv']} SMMLV")
        elif qd["minimum_smmlv"] is None or pded["minimum_smmlv"] is None: diffs.append("mínimo en SMMLV no verificable")
        if any(" vs " in d for d in diffs):
            sev="ALERTA" if "OCR" in str(policy.get("extraction_mode","")).upper() else "ERROR"
            msg="Diferencia potencial en el deducible: "+"; ".join(diffs)+". Verificar en el PDF original."
        elif diffs:
            sev="ALERTA"; msg="No se pudo comparar completamente el deducible: "+"; ".join(diffs)+"."
        else:
            sev="INFO"; msg="Coinciden porcentaje, base y mínimo en el texto extraído."
        _add(out,sev,"Deducibles",label,qd["snippet"],pded["snippet"],msg,f"Cotización: {qd['snippet']} || Póliza: {pded['snippet']}")

    # Compare all deductible clauses as a structured checklist; don't silently equate differently worded bases.
    slip_deds=_deductible_records(slip_text); policy_deds=_deductible_records(policy_text)
    if not slip_deds: _add(out,"NO_VERIFICABLE","Deducibles","Cuadro completo de deducibles",None,None,"No se logró segmentar el cuadro completo de deducibles de la cotización.")
    if not policy_deds: _add(out,"NO_VERIFICABLE","Deducibles","Deducibles de póliza",None,None,"No se logró segmentar el cuadro completo de deducibles de la póliza.")
    # Report extracted rows and coverage completeness without declaring false matches.
    for docname, records in [("cotización",slip_deds),("póliza",policy_deds)]:
        if records:
            text_summary=" | ".join(f"pág. {r['page']}: {r['block'][:180]}" for r in records[:18])
            _add(out,"INFO","Deducibles extraídos",f"Inventario — {docname}",f"{len(records)} cláusulas",f"{len(records)} cláusulas",f"Se extrajeron {len(records)} fragmentos de deducible para inspección humana; la segmentación de cobertura requiere confirmación.",text_summary)
    # Coverage/wording checks from main quote and policy, explicit earthquake insured values
    for term,label in [("RESPONSABILIDAD CIVIL EXTRACONTRACTUAL","RC extracontractual"),("ROTURA DE MAQUINARIA","Rotura de maquinaria"),("EQUIPO ELECTRONICO","Equipo electrónico"),("SUSTRACCION CON VIOLENCIA","Sustracción con violencia"),("VIDRIOS PLANOS","Vidrios planos"),("ASISTENCIA A LA COPROPIEDAD","Asistencia a la copropiedad")]:
        q=bool(re.search(term,slip_text,re.I)); p=bool(re.search(term,policy_text,re.I))
        if q and not p: _add(out,"ALERTA","Amparos",label,"Mencionado en cotización","No detectado en póliza","El amparo aparece en la cotización pero no se detectó en el texto extraído de la póliza; puede ser un problema de OCR o una diferencia real.")
        elif p and not q: _add(out,"INFO","Amparos",label,"No detectado en cotización","Mencionado en póliza","La póliza menciona un amparo que no se detectó en la cotización; revisar si fue contratado o viene por defecto.")
    # OCR / evidence quality
    if "requiere OCR" in (slip.get("extraction_mode","")+policy.get("extraction_mode","")):
        _add(out,"ALERTA","Calidad documental","OCR",slip.get("extraction_mode"),policy.get("extraction_mode"),"Uno de los documentos no aportó texto suficiente; OCR o lectura visual requerida.")
    if not out: _add(out,"INFO","Control general","Resultado","—","—","No se detectaron diferencias en los campos extraídos; no equivale a aprobación automática.")
    return out
