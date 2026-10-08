"""Operadores de condição. Comparações simples de texto — sem expressões arbitrárias."""
import unicodedata

OPERATORS = {
    "contains": "contém",
    "not_contains": "não contém",
    "contains_any": "contém alguma das palavras (separe por vírgula)",
    "equals": "é igual a",
    "not_equals": "é diferente de",
    "starts_with": "começa com",
    "ends_with": "termina com",
    "is_empty": "está vazio",
    "is_not_empty": "não está vazio",
}
UNARY_OPERATORS = {"is_empty", "is_not_empty"}


def _normalize(text: str, case_sensitive: bool) -> str:
    text = (text or "").strip()
    if case_sensitive:
        return text
    # Ignora maiúsculas e acentos: "Preço" == "preco"
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def evaluate(left: str, operator: str, right: str, case_sensitive: bool = False) -> bool:
    if operator not in OPERATORS:
        raise ValueError(f"Operador desconhecido: {operator}")
    a = _normalize(left, case_sensitive)
    b = _normalize(right, case_sensitive)
    match operator:
        case "contains":
            return b in a
        case "not_contains":
            return b not in a
        case "contains_any":
            words = [w for w in (_normalize(x, case_sensitive) for x in (right or "").split(",")) if w]
            return any(w in a for w in words)
        case "equals":
            return a == b
        case "not_equals":
            return a != b
        case "starts_with":
            return a.startswith(b)
        case "ends_with":
            return a.endswith(b)
        case "is_empty":
            return a == ""
        case "is_not_empty":
            return a != ""
    return False
