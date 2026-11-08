import pytest
from app.analyzers.metamorphic_comer import MetamorphicComerEngine

def test_comer_function_extraction():
    code = """
def calculate_sum(items):
    return sum(items)

def _private_func():
    pass
"""
    engine = MetamorphicComerEngine()
    funcs = engine.extract_testable_functions(code)
    assert len(funcs) == 1
    assert funcs[0]["name"] == "calculate_sum"
    assert funcs[0]["params"] == ["items"]

def test_comer_metamorphic_group_generation():
    engine = MetamorphicComerEngine()
    func_info = {"name": "sort_data", "params": ["items"]}
    src, fol = engine.generate_metamorphic_group(func_info, "PERMUTE")
    assert "items" in src
    assert "items" in fol
    assert sorted(src["items"]) == sorted(fol["items"])

def test_comer_permutation_invariance_verification():
    engine = MetamorphicComerEngine()
    # Permutation invariant should hold for sum
    violated, msg = engine.verify_metamorphic_relation(
        func_name="sum_items",
        relation_type="PERMUTE",
        src_in={"items": [1, 2, 3]},
        fol_in={"items": [3, 1, 2]},
        src_out=6,
        fol_out=6
    )
    assert violated is False
    assert "satisfied" in msg

def test_comer_detects_order_dependent_invariant_violation():
    engine = MetamorphicComerEngine()
    # Broken function where output changed from 14 to 10 on permutation
    violated, msg = engine.verify_metamorphic_relation(
        func_name="bad_checksum",
        relation_type="PERMUTE",
        src_in={"items": [1, 2, 3]},
        fol_in={"items": [3, 2, 1]},
        src_out=14,
        fol_out=10
    )
    assert violated is True
    assert "Permutation Invariant Violated" in msg
