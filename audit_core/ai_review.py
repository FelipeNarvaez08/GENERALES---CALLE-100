from __future__ import annotations
import requests

def ollama_review(slip_text: str, policy_text: str, model: str="qwen2.5:7b", base_url: str="http://localhost:11434", timeout: int=90):
    """Optional local semantic comparison. Never treat the model's output as authoritative."""
    prompt = f'''Eres un asistente de auditoría técnica de seguros. Compara el slip de cotización con la póliza emitida.
No inventes valores. Distingue diferencia comprobable, alerta por ambigüedad y no verificable. Cita texto breve y página si aparece en los documentos. Devuelve una lista JSON de objetos con claves: severidad (ERROR/ALERTA/NO_VERIFICABLE), campo, slip, poliza, hallazgo, evidencia. No des aprobación final.

SLIP:
{slip_text[:24000]}

PÓLIZA:
{policy_text[:24000]}
'''
    response = requests.post(f"{base_url.rstrip('/')}/api/generate", json={"model":model,"prompt":prompt,"stream":False,"format":"json"}, timeout=timeout)
    response.raise_for_status()
    return response.json().get("response", "")
