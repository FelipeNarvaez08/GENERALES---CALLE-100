from audit_core.rules import audit_pair

def test_nit_format_and_name_suffix_do_not_create_false_error():
    slip={"policyholder":"EDIFICIO TRASTEVERE PH","insured":"EDIFICIO TRASTEVERE PH","beneficiary":"EDIFICIO TRASTEVERE PH","nit":"830,020,130","validity_text":"Anual desde fecha a convenir","sum_insured":"4,883,576,546","premium":None,"tax":None,"total_payable":None}
    policy={"policyholder":"EDIFICIO TRASTEVERE","insured":"EDIFICIO TRASTEVERE","beneficiary":"EDIFICIO TRASTEVERE","nit":"830.020.130-6","start_date":"10/10/2026","end_date":"10/10/2027","sum_insured":None,"premium":None,"tax":None,"total_payable":None,"extraction_mode":"text"}
    out=audit_pair(slip,policy,""," ")
    assert not any(x["Severidad"]=="ERROR" and x["Campo"] in ("Tomador","Asegurado","Beneficiario","NIT") for x in out)
    assert any(x["Campo"]=="Vigencia del seguro" for x in out)
    assert any(x["Campo"]=="Prima" for x in out)
