from pathlib import Path
from audit_core.extract import extract_pdf, extract_fields
from audit_core.rules import audit_pair

ROOT = Path(__file__).resolve().parents[1]

def test_trastevere_sample_extraction_and_initial_findings():
    slip_doc = extract_pdf((ROOT / "muestras" / "Cotizacion_Cop_v1(2).pdf").read_bytes(), "slip.pdf")
    policy_doc = extract_pdf((ROOT / "muestras" / "Pol_Cop_101001320(1).pdf").read_bytes(), "policy.pdf")
    slip = extract_fields(slip_doc, "slip")
    policy = extract_fields(policy_doc, "policy")
    assert slip["slip_number"] == "17543237"
    assert slip["sum_insured"] == "4,883,576,546"
    assert policy["policy_number"] == "33-22-101001320"
    assert policy["start_date"] == "10/10/2026"
    assert policy["end_date"] == "10/10/2027"
    findings = audit_pair(slip, policy, slip_doc.text, policy_doc.text)
    assert any(x["Campo"] == "Vigencia del seguro" and x["Severidad"] == "ALERTA" for x in findings)
    assert any(x["Campo"] == "NIT" and x["Severidad"] == "ALERTA" for x in findings)
    assert not any(x["Severidad"] == "ERROR" and x["Campo"] in ("Tomador", "Asegurado", "Beneficiario") for x in findings)
