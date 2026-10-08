import pytest

from app.workflow.conditions import evaluate
from app.workflow.template import render, truncate_utf8

CTX = {
    "message": {"text": "Qual o preço?"},
    "contact": {"username": "maria", "name": "Maria"},
    "ai": {"response": "R$ 10"},
    "vars": {"cupom": "PROMO10", "nested": {"a": 1}},
    "_sys": {"account_id": "secret-internal"},
}


def test_render_replaces_known_variables():
    assert render("Oi @{{contact.username}}! {{ message.text }}", CTX) == "Oi @maria! Qual o preço?"


def test_render_user_alias_maps_to_contact():
    assert render("{{user.name}}", CTX) == "Maria"


def test_render_missing_variable_becomes_empty():
    assert render("[{{vars.nao_existe}}]", CTX) == "[]"


def test_render_never_exposes_internal_keys():
    assert render("{{_sys.account_id}}", CTX) == ""
    assert render("{{vars._x}}", {"vars": {"_x": "segredo"}}) == ""


def test_render_does_not_evaluate_code():
    payload = "{{ __import__('os').system('echo hacked') }}"
    assert render(payload, CTX) == payload
    assert render("{{message.text.__class__}}", CTX) == ""


def test_render_dict_value_as_json():
    assert render("{{vars.nested}}", CTX) == '{"a": 1}'


def test_truncate_utf8_keeps_valid_characters():
    text = "ã" * 600  # 1200 bytes
    out = truncate_utf8(text, 1000)
    assert len(out.encode()) <= 1000
    assert out == "ã" * 500


@pytest.mark.parametrize(
    "left,op,right,expected",
    [
        ("Qual o PREÇO?", "contains", "preco", True),
        ("Qual o PREÇO?", "contains", "preco", True),
        ("oi", "not_contains", "preço", True),
        ("Quero o link", "contains_any", "link, catálogo", True),
        ("Quero o catalogo", "contains_any", "link, catálogo", True),
        ("bom dia", "contains_any", "link, catálogo", False),
        ("SIM", "equals", "sim", True),
        ("sim", "not_equals", "não", True),
        ("Olá mundo", "starts_with", "ola", True),
        ("Olá mundo", "ends_with", "MUNDO", True),
        ("   ", "is_empty", "", True),
        ("x", "is_not_empty", "", True),
    ],
)
def test_condition_operators(left, op, right, expected):
    assert evaluate(left, op, right) is expected


def test_condition_case_sensitive():
    assert evaluate("Preço", "contains", "preço", case_sensitive=True) is False
    assert evaluate("Preço", "contains", "Preço", case_sensitive=True) is True


def test_condition_unknown_operator():
    with pytest.raises(ValueError):
        evaluate("a", "regex", ".*")
