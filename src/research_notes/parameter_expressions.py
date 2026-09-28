"""Bounded dimensional arithmetic and explicit bindings to model parameters."""
from __future__ import annotations

import ast
import math
import re
from dataclasses import dataclass, replace

from research_notes.deterministic_recompute import FeatureModel, validate_model

# Base quantities are millimetres and radians. Angle remains an explicit dimension.
UNITS = {"one": (1., (0, 0)), "mm": (1., (1, 0)), "cm": (10., (1, 0)),
         "m": (1000., (1, 0)), "inch": (25.4, (1, 0)),
         "rad": (1., (0, 1)), "deg": (math.pi / 180, (0, 1))}


@dataclass(frozen=True)
class Parameter:
    name: str
    expression: str
    unit: str = "mm"
    lower: float = -10000.
    upper: float = 10000.


@dataclass(frozen=True)
class Quantity:
    value: float
    dimension: tuple[int, int]


@dataclass(frozen=True)
class ParameterValue:
    name: str
    expression: str
    declared_unit: str
    value_in_declared_unit: float
    base_value: float
    dimension: tuple[int, int]
    dependencies: tuple[str, ...]


def _tree(expression: str) -> ast.Expression:
    if not isinstance(expression, str) or not 1 <= len(expression) <= 256:
        raise ValueError("expression must contain 1..256 characters")
    try:
        tree = ast.parse(expression, mode="eval")
    except (SyntaxError, RecursionError) as exc:
        raise ValueError("invalid expression syntax") from exc
    nodes = list(ast.walk(tree))
    if len(nodes) > 96:
        raise ValueError("expression exceeds 96 AST nodes")
    allowed = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Add, ast.Sub,
               ast.Mult, ast.Div, ast.UAdd, ast.USub, ast.Constant, ast.Name, ast.Load)
    if any(not isinstance(n, allowed) for n in nodes):
        raise ValueError("only names, numbers, parentheses, +, -, *, and / are supported")
    return tree


def _evaluate(node: ast.AST, values: dict[str, Quantity]) -> Quantity:
    if isinstance(node, ast.Expression):
        return _evaluate(node.body, values)
    if isinstance(node, ast.Name):
        return values[node.id]
    if isinstance(node, ast.Constant):
        if type(node.value) not in (int, float):
            raise ValueError("only real numeric literals are supported")
        result = Quantity(float(node.value), (0, 0))
    elif isinstance(node, ast.UnaryOp):
        item = _evaluate(node.operand, values)
        result = Quantity((-1 if isinstance(node.op, ast.USub) else 1) * item.value, item.dimension)
    else:
        a, b = _evaluate(node.left, values), _evaluate(node.right, values)
        if isinstance(node.op, (ast.Add, ast.Sub)):
            if a.dimension != b.dimension:
                raise ValueError("addition/subtraction requires equal dimensions")
            result = Quantity(a.value + (b.value if isinstance(node.op, ast.Add) else -b.value), a.dimension)
        elif isinstance(node.op, ast.Mult):
            result = Quantity(a.value * b.value, tuple(x+y for x, y in zip(a.dimension, b.dimension)))
        else:
            if b.value == 0:
                raise ValueError("division by zero")
            result = Quantity(a.value / b.value, tuple(x-y for x, y in zip(a.dimension, b.dimension)))
    if not math.isfinite(result.value) or abs(result.value) > 1e12 or any(abs(d) > 4 for d in result.dimension):
        raise ValueError("quantity exceeds the finite arithmetic domain")
    return result


def evaluate_parameters(parameters: tuple[Parameter, ...]) -> tuple[ParameterValue, ...]:
    """Evaluate a named DAG without eval(), implicit units, or external lookup."""
    if not 1 <= len(parameters) <= 64:
        raise ValueError("parameter table must contain 1..64 entries")
    by_name = {p.name: p for p in parameters}
    if len(by_name) != len(parameters):
        raise ValueError("duplicate parameter name")
    trees, dependencies = {}, {}
    for p in parameters:
        if not re.fullmatch(r"[a-z][a-z0-9_]*", p.name) or p.name in UNITS:
            raise ValueError("parameter name is invalid or reserved")
        if p.unit not in UNITS:
            raise ValueError("unsupported declared unit")
        if not all(math.isfinite(v) and abs(v) <= 1e12 for v in (p.lower, p.upper)) or p.lower > p.upper:
            raise ValueError("invalid inclusive parameter domain")
        trees[p.name] = _tree(p.expression)
        names = {n.id for n in ast.walk(trees[p.name]) if isinstance(n, ast.Name)}
        unknown = names - by_name.keys() - UNITS.keys()
        if unknown:
            raise ValueError("unknown expression name: " + sorted(unknown)[0])
        dependencies[p.name] = tuple(sorted(names - UNITS.keys()))
    values = {key: Quantity(*data) for key, data in UNITS.items()}
    results = {}
    remaining = set(by_name)
    while remaining:
        ready = sorted(name for name in remaining if all(d in results for d in dependencies[name]))
        if not ready:
            raise ValueError("cyclic parameter expressions")
        for name in ready:
            p = by_name[name]
            q = _evaluate(trees[name], values)
            scale, dimension = UNITS[p.unit]
            if q.dimension != dimension:
                raise ValueError("expression dimension differs from declared unit: " + name)
            converted = q.value / scale
            if not p.lower <= converted <= p.upper:
                raise ValueError("parameter is outside its inclusive domain: " + name)
            results[name] = ParameterValue(name, p.expression, p.unit, converted, q.value, q.dimension, dependencies[name])
            values[name] = q
        remaining.difference_update(ready)
    return tuple(results[p.name] for p in parameters)


def bind_model_parameters(model: FeatureModel, parameters: tuple[Parameter, ...],
                          bindings: tuple[tuple[str, str, str], ...]) -> FeatureModel:
    """Bind (parameter name, node ID, dimension name); all v0.60 model inputs are mm."""
    validate_model(model)
    if model.provenance == "unconfirmed_candidate":
        raise ValueError("confirm candidate selection before binding dimensions")
    values = {v.name: v for v in evaluate_parameters(parameters)}
    nodes = {n.node_id: n for n in model.nodes}
    seen = set()
    for name, node_id, field in bindings:
        if name not in values or node_id not in nodes or field not in dict(nodes[node_id].parameters):
            raise ValueError("unresolved parameter binding")
        if (node_id, field) in seen:
            raise ValueError("duplicate target binding")
        seen.add((node_id, field))
        if values[name].dimension != (1, 0):
            raise ValueError("model dimensions require a length quantity")
        node = nodes[node_id]
        nodes[node_id] = replace(node, parameters=tuple((k, values[name].base_value if k == field else v) for k, v in node.parameters))
    result = replace(model, nodes=tuple(nodes[n.node_id] for n in model.nodes), revision=model.revision + 1)
    validate_model(result)
    return result
