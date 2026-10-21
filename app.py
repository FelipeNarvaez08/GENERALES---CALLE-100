from __future__ import annotations
import json, hashlib, io, os
import streamlit as st
import pandas as pd
from audit_core.extract import extract_pdf, extract_fields
from audit_core.rules import audit_pair
from audit_core.ai_review import ollama_review
from audit_core.reporting import to_excel

st.set_page_config(page_title="Auditoría técnica de pólizas", page_icon="🛡️", layout="wide")
st.title("🛡️ Auditoría técnica de pólizas")
st.caption("Copropiedades · Comparación de cotización vs. póliza · Reglas determinísticas + IA opcional + validación humana")

with st.sidebar:
    st.header("Configuración")
    product=st.selectbox("Módulo de producto",["Copropiedades","Copropiedades + D&O","PYME (en preparación)","Hogar (en preparación)","RCE (en preparación)"])
    enable_ocr=st.toggle("Activar OCR complementario en tablas escaneadas",value=True,help="Lee por OCR las primeras tres páginas/tablas donde suelen estar los valores y deducibles.")
    full_ocr=st.toggle("OCR completo de todos los folios (más lento)",value=False,help="Actívalo para revisar clausulados y anexos escaneados en todo el PDF.")
    st.divider(); st.subheader("IA local opcional")
    use_ai=st.toggle("Ejecutar revisión semántica con Ollama",value=False)
    ollama_model=st.text_input("Modelo Ollama",value="qwen2.5:7b",disabled=not use_ai)
    ollama_url=st.text_input("URL base de Ollama",value=os.getenv("OLLAMA_BASE_URL","http://localhost:11434"),disabled=not use_ai,help="La URL debe ser accesible desde la máquina o contenedor que ejecuta Streamlit.")
    st.caption("Las reglas funcionan sin IA. La IA solo propone hallazgos y no aprueba ni rechaza una póliza.")
    st.divider()
    st.warning("No cargues pólizas reales en una instancia pública sin aprobación de seguridad de la compañía. Este paquete piloto aún no tiene login corporativo ni base de datos multiusuario.")

st.markdown("### 1. Cargar documentos")
c1,c2=st.columns(2)
with c1: slip_files=st.file_uploader("Cotizaciones / slips PDF",type=["pdf"],accept_multiple_files=True,key="slips")
with c2: policy_files=st.file_uploader("Pólizas emitidas PDF",type=["pdf"],accept_multiple_files=True,key="policies")
if not slip_files or not policy_files:
    st.info("Carga al menos un slip y una póliza. Caso de prueba: carpeta `muestras/` dentro del proyecto.")
    st.markdown("El módulo de Copropiedades revisa identificación, ubicación, vigencia, valores económicos, amparos detectables y deducibles. Para terremoto valida por separado porcentaje, base de cálculo (valor asegurable vs. valor de la pérdida) y mínimo en SMMLV.")
    st.stop()
if len(slip_files)>20 or len(policy_files)>20:
    st.error("Máximo 20 slips y 20 pólizas por tanda. Divide la carga en grupos más pequeños."); st.stop()

slip_map={f.name:f for f in slip_files}; policy_map={f.name:f for f in policy_files}
with st.expander("2. Asociar cada cotización con su póliza",expanded=True):
    st.caption("Emparejamiento manual para evitar comparar documentos de riesgos diferentes.")
    a,b=st.columns(2)
    with a: chosen_slip=st.selectbox("Slip",list(slip_map),key="chosen_slip")
    with b: chosen_policy=st.selectbox("Póliza",list(policy_map),key="chosen_policy")
    if "pairs" not in st.session_state: st.session_state.pairs=[]
    if st.button("＋ Agregar par"):
        if any(p["slip"]==chosen_slip or p["policy"]==chosen_policy for p in st.session_state.pairs): st.warning("Ese slip o esa póliza ya pertenece a otro par.")
        else: st.session_state.pairs.append({"slip":chosen_slip,"policy":chosen_policy}); st.rerun()
    if st.session_state.pairs:
        st.dataframe(pd.DataFrame(st.session_state.pairs),use_container_width=True,hide_index=True)
        rm=st.selectbox("Par a retirar",["(ninguno)"]+[f"{i+1}. {p['slip']} ↔ {p['policy']}" for i,p in enumerate(st.session_state.pairs)])
        x,y=st.columns(2)
        with x:
            if st.button("Retirar par seleccionado") and rm!="(ninguno)": st.session_state.pairs.pop(int(rm.split(".")[0])-1); st.rerun()
        with y:
            if st.button("Vaciar asociaciones"): st.session_state.pairs=[]; st.rerun()
    else: st.warning("Aún no hay pares asociados.")
if not st.session_state.pairs: st.stop()

if st.button("🔎 Ejecutar auditoría completa",type="primary",use_container_width=True):
    all_findings=[]; summaries=[]; extracted=[]
    progress=st.progress(0,text="Preparando documentos…")
    for i,pair in enumerate(st.session_state.pairs):
        sd=extract_pdf(slip_map[pair["slip"]].getvalue(),pair["slip"],enable_ocr=enable_ocr,full_ocr=full_ocr)
        pd_doc=extract_pdf(policy_map[pair["policy"]].getvalue(),pair["policy"],enable_ocr=enable_ocr,full_ocr=full_ocr)
        sf=extract_fields(sd,"slip"); pf=extract_fields(pd_doc,"policy")
        findings=audit_pair(sf,pf,sd.text,pd_doc.text)
        for f in findings:
            f.update({"Negocio":sf.get("insured") or sf.get("policyholder") or pair["slip"],"Archivo slip":pair["slip"],"Archivo póliza":pair["policy"],"Producto":product,"Origen":"Reglas determinísticas"})
        ai_status="No ejecutada"
        if use_ai:
            try:
                raw=ollama_review(sd.text,pd_doc.text,ollama_model,ollama_url)
                parsed=json.loads(raw); parsed=parsed.get("hallazgos",parsed.get("findings",[])) if isinstance(parsed,dict) else parsed
                if not isinstance(parsed,list): raise ValueError("La respuesta JSON no contiene una lista de hallazgos")
                ai_status=f"Ejecutada: {len(parsed)} propuestas"
                for item in parsed:
                    if not isinstance(item,dict): continue
                    f={"Severidad":str(item.get("severidad","ALERTA")).upper(),"Categoría":item.get("categoria","IA semántica"),"Campo":item.get("campo","Por revisar"),"Slip / cotización":item.get("slip","No identificado"),"Póliza emitida":item.get("poliza","No identificado"),"Hallazgo":item.get("hallazgo","Propuesta de IA"),"Evidencia / contexto":item.get("evidencia","Sin evidencia explícita"),"Estado humano":"Pendiente","Comentario del revisor":"","Negocio":sf.get("insured") or pair["slip"],"Archivo slip":pair["slip"],"Archivo póliza":pair["policy"],"Producto":product,"Origen":"IA (requiere confirmación humana)"}
                    all_findings.append(f)
            except Exception as e:
                ai_status=f"No disponible: {str(e)[:140]}"
                all_findings.append({"Severidad":"ALERTA","Categoría":"IA semántica","Campo":"Conexión / respuesta Ollama","Slip / cotización":"—","Póliza emitida":"—","Hallazgo":"No se pudo usar Ollama. La auditoría determinística sí continúa.","Evidencia / contexto":ai_status,"Estado humano":"Pendiente","Comentario del revisor":"","Negocio":sf.get("insured") or pair["slip"],"Archivo slip":pair["slip"],"Archivo póliza":pair["policy"],"Producto":product,"Origen":"IA"})
        all_findings.extend(findings)
        summaries.append({"Negocio":sf.get("insured") or sf.get("policyholder") or pair["slip"],"N.º cotización":sf.get("slip_number"),"N.º póliza":pf.get("policy_number"),"Slip":pair["slip"],"Póliza":pair["policy"],"N.º hallazgos":len(findings),"Errores":sum(x["Severidad"]=="ERROR" for x in findings),"Alertas":sum(x["Severidad"]=="ALERTA" for x in findings),"No verificables":sum(x["Severidad"]=="NO_VERIFICABLE" for x in findings),"OCR slip":sf.get("extraction_mode"),"OCR póliza":pf.get("extraction_mode"),"IA":ai_status,"Estado de auditoría":"Revisión humana pendiente"})
        extracted.append({"Negocio":sf.get("insured") or pair["slip"],"Slip":pair["slip"],"Póliza":pair["policy"],"Campos slip":sf,"Campos póliza":pf,"Texto slip":sd.text,"Texto póliza":pd_doc.text})
        progress.progress((i+1)/len(st.session_state.pairs),text=f"Auditando negocio {i+1} de {len(st.session_state.pairs)}…")
    st.session_state.audit_findings=all_findings; st.session_state.audit_summary=summaries; st.session_state.audit_extracted=extracted; st.session_state.audit_product=product
    # Stable unique run id for export traceability, no document content is logged.
    st.session_state.audit_id=hashlib.sha256(("|".join(p["slip"]+p["policy"] for p in st.session_state.pairs)).encode()).hexdigest()[:12]

if "audit_findings" in st.session_state:
    findings=st.session_state.audit_findings; summaries=st.session_state.audit_summary
    st.divider(); st.markdown("### 3. Tablero de auditoría")
    fdf=pd.DataFrame(findings); sdf=pd.DataFrame(summaries)
    sev=fdf.get("Severidad",pd.Series(dtype=str))
    k1,k2,k3,k4,k5=st.columns(5)
    k1.metric("Negocios",len(summaries)); k2.metric("Errores",int((sev=="ERROR").sum())); k3.metric("Alertas",int((sev=="ALERTA").sum())); k4.metric("No verificables",int((sev=="NO_VERIFICABLE").sum())); k5.metric("Pendientes humanos",int((fdf.get("Estado humano",pd.Series(dtype=str))=="Pendiente").sum()))
    st.dataframe(sdf,use_container_width=True,hide_index=True)
    st.markdown("#### Hallazgos: filtrar, revisar y decidir")
    if not fdf.empty:
        fc1,fc2,fc3=st.columns(3)
        with fc1: selected_sev=st.multiselect("Severidad",[x for x in ["ERROR","ALERTA","NO_VERIFICABLE","INFO"] if x in set(sev)],default=[x for x in ["ERROR","ALERTA","NO_VERIFICABLE"] if x in set(sev)])
        with fc2: selected_cat=st.multiselect("Categoría",sorted(fdf["Categoría"].dropna().astype(str).unique().tolist()),default=sorted(fdf["Categoría"].dropna().astype(str).unique().tolist()))
        with fc3: selected_state=st.multiselect("Estado humano",sorted(fdf["Estado humano"].dropna().astype(str).unique().tolist()),default=sorted(fdf["Estado humano"].dropna().astype(str).unique().tolist()))
        view=fdf[fdf["Severidad"].isin(selected_sev)&fdf["Categoría"].isin(selected_cat)&fdf["Estado humano"].isin(selected_state)].copy()
        editable=st.data_editor(view,use_container_width=True,hide_index=True,key="review_editor",column_config={"Estado humano":st.column_config.SelectboxColumn("Estado humano",options=["Pendiente","Confirmado","Falso positivo","Corregido","No aplica"],required=True),"Comentario del revisor":st.column_config.TextColumn("Comentario del revisor",width="large"),"Hallazgo":st.column_config.TextColumn("Hallazgo",width="large"),"Evidencia / contexto":st.column_config.TextColumn("Evidencia / contexto",width="large")},disabled=[c for c in view.columns if c not in ["Estado humano","Comentario del revisor"]])
        if st.button("Guardar validación humana",type="secondary"):
            for idx,row in editable.iterrows():
                if 0<=int(idx)<len(st.session_state.audit_findings):
                    st.session_state.audit_findings[int(idx)]["Estado humano"]=row["Estado humano"]
                    st.session_state.audit_findings[int(idx)]["Comentario del revisor"]=row["Comentario del revisor"]
            st.success("Validación guardada en esta sesión. Descarga el Excel para conservar el resultado fuera de la sesión."); st.rerun()
    st.markdown("#### Campos extraídos para contraste")
    for i,item in enumerate(st.session_state.audit_extracted):
        with st.expander(f"{i+1}. {item['Negocio']} — {item['Slip']} / {item['Póliza']}"):
            c1,c2=st.columns(2)
            with c1: st.write("**Cotización**"); st.json(item["Campos slip"])
            with c2: st.write("**Póliza emitida**"); st.json(item["Campos póliza"])
    excel=to_excel(st.session_state.audit_findings,st.session_state.audit_summary,st.session_state.audit_extracted)
    st.download_button("⬇️ Descargar informe Excel completo",data=excel,file_name=f"auditoria_copropiedades_{st.session_state.get('audit_id','resultado')}.xlsx",mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",type="primary",use_container_width=True)
    with st.expander("Alcance y límites importantes"):
        st.markdown("- La comparación de terremoto trata por separado el porcentaje, la base de cálculo (valor asegurable del artículo afectado o valor de la pérdida) y el mínimo en SMMLV. La evidencia OCR puede contener errores; el revisor debe confirmar la redacción en el PDF original.\n- El inventario de deducibles se extrae para facilitar la revisión; la asociación de cada cláusula a cada amparo no se considera infalible en todos los formatos.\n- La detección de amparos es un control de presencia textual, no una interpretación legal completa de exclusiones, garantías o clausulados.\n- Ningún hallazgo ni ausencia de hallazgos constituye aprobación automática de la póliza.")
