from audit_core.rules import parse_money
from audit_core.rules_copropiedades import _earthquake_deductible

def test_money_parser_handles_thousands_and_decimal_cents():
    assert parse_money("210,403,531.00") == 210403531
    assert parse_money("8,641,553") == 8641553

def test_earthquake_deductible_extracts_base_and_smmlv_floor():
    slip = "[PÁGINA 3]\n3% APLICABLE AL VALOR ASEGURABLE DE CADA UNO DE LOS ARTICULOS AFECTADOS POR SINIESTRO, SIN SER INFERIOR A 3 SMMLV Terremoto, Temblor de tierra y/o erupción Volcánica"
    policy = "[PÁGINA 2]\nTERREMOTO, TEMBLOR Y/O ERUPCION VOLCANICA $ 4,641,888,371.00 DEDUCIBLES: 3.00 % EL VALOR ASEGURABLE DE C/ART AFECTADO POR EL SINI - Minimo: 3.00 SMMLV en TERREMOTO"
    a = _earthquake_deductible(slip)
    b = _earthquake_deductible(policy)
    assert a["percent"] == b["percent"] == 3.0
    assert a["base"] == b["base"] == "valor asegurable"
    assert a["minimum_smmlv"] == b["minimum_smmlv"] == 3.0
