from __future__ import annotations
from io import BytesIO
import pandas as pd

def to_excel(findings, summary=None, extracted=None):
    buffer=BytesIO(); df=pd.DataFrame(findings)
    if df.empty: df=pd.DataFrame(columns=["Severidad","Categoría","Campo","Slip / cotización","Póliza emitida","Hallazgo","Evidencia / contexto","Estado humano","Comentario del revisor"])
    with pd.ExcelWriter(buffer,engine="openpyxl") as writer:
        df.to_excel(writer,index=False,sheet_name="Hallazgos")
        if summary is not None: pd.DataFrame(summary).to_excel(writer,index=False,sheet_name="Resumen")
        if extracted:
            rows=[]
            for item in extracted:
                for source in ["Campos slip","Campos póliza"]:
                    for field,value in item.get(source,{}).items():
                        rows.append({"Negocio":item.get("Negocio"),"Archivo":item.get("Slip") if source=="Campos slip" else item.get("Póliza"),"Documento":source,"Campo":field,"Valor extraído":str(value) if value is not None else ""})
            pd.DataFrame(rows).to_excel(writer,index=False,sheet_name="Campos extraídos")
        for ws in writer.book.worksheets:
            ws.freeze_panes="A2"; ws.auto_filter.ref=ws.dimensions
            for col in ws.columns:
                max_len=max((len(str(c.value or "")) for c in col[:200]),default=10)
                ws.column_dimensions[col[0].column_letter].width=min(max(max_len+2,12),60)
    buffer.seek(0); return buffer.getvalue()
