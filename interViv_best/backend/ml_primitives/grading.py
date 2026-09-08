"""Pure evidence over source and supplied outputs. No source is executed here.

OracleSuite contains trusted, already prepared cases/reference outputs and
property callables. Only tests prepare suites in this phase. AST findings are
signals about syntax, not proofs of numerical correctness or sandbox safety.
"""

import ast
from dataclasses import dataclass
from typing import Callable, Mapping

import numpy as np


@dataclass(frozen=True)
class Tolerance:
    rtol: float
    atol: float

    def __post_init__(self):
        if not all(np.isfinite(v) and v >= 0 for v in (self.rtol, self.atol)):
            raise ValueError("Tolerances must be explicit, finite and nonnegative.")

    def close(self, actual, expected):
        return bool(np.allclose(actual, expected, rtol=self.rtol, atol=self.atol,
                                equal_nan=False))


@dataclass(frozen=True)
class OracleCase:
    id: str
    inputs: dict
    reference_output: object


@dataclass(frozen=True)
class OracleSuite:
    problem_id: str
    version: int
    seed: int
    tolerance: Tolerance
    cases: tuple[OracleCase, ...]
    properties: Mapping[str, Callable]
    static_rules: dict


def _leaves(actual, expected):
    """Match nested named outputs without broadcasting or dropping fields."""
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or actual.keys() != expected.keys():
            raise ValueError("Output structure differs.")
        return [pair for key in sorted(expected)
                for pair in _leaves(actual[key], expected[key])]
    if not isinstance(actual, np.ndarray) or not isinstance(expected, np.ndarray):
        raise ValueError("Output leaves must be NumPy arrays, including scalar arrays.")
    return [(actual, expected)]


def grade(submitted_source: str, executed_outputs: Mapping[str, object], *, suite: OracleSuite):
    """Return per-case properties and static findings, never a combined score.

    A complete output envelope is required. Missing execution is an unavailable
    infrastructure input, not a failed candidate property. Outputs can only
    originate from trusted pack tests today; no API accepts this envelope.
    """
    ids = [case.id for case in suite.cases]
    if not ids or len(set(ids)) != len(ids) or set(executed_outputs) != set(ids):
        raise ValueError("A complete, uniquely keyed executed-output envelope is required.")
    reserved = {"shape", "dtype", "reference agreement"}
    if reserved & suite.properties.keys():
        raise ValueError("Pack properties must not overwrite structural checks.")
    names = ["shape", "dtype", "reference agreement", *suite.properties]
    findings = {name: [] for name in names}
    for case in suite.cases:
        actual = executed_outputs[case.id]
        try:
            pairs = _leaves(actual, case.reference_output)
            shape = all(a.shape == e.shape for a, e in pairs)
            dtype = all(a.dtype == e.dtype for a, e in pairs)
            agrees = shape and all(suite.tolerance.close(a, e) for a, e in pairs)
        except (ValueError, TypeError):
            shape = dtype = agrees = False
        values = {"shape": shape, "dtype": dtype, "reference agreement": agrees}
        for name, check in suite.properties.items():
            # Malformed outputs should report the named property, not leak an
            # exception/string containing hidden inputs into an evidence record.
            try:
                values[name] = bool(check(case.inputs, actual, suite.tolerance))
            except (ValueError, TypeError, IndexError, KeyError, AttributeError,
                    FloatingPointError, ZeroDivisionError):
                values[name] = False
        for name, passed in values.items():
            findings[name].append({"case_id": case.id, "passed": bool(passed)})
    return {
        "problem_id": suite.problem_id, "version": suite.version, "seed": suite.seed,
        "tolerance": {"rtol": suite.tolerance.rtol, "atol": suite.tolerance.atol},
        "properties": [{"name": name, "passed": all(c["passed"] for c in cases),
                        "cases": cases} for name, cases in findings.items()],
        "static": static_signals(submitted_source, suite.static_rules),
    }


def static_signals(source: str, config: dict):
    """Interpret pack rules using ast only; never import candidate modules.

    Alias/assignment tracking is lexical within a function. Branch-sensitive
    dataflow and arbitrary helper-function semantics are outside these signals.
    """
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError) as exc:
        return {"syntax_error": {"line": getattr(exc, "lineno", None) or 1}, "findings": []}

    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}

    def scope(node):
        while node in parents:
            node = parents[node]
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                return node
        return tree

    aliases = {}
    findings = set()
    imports = config["imports"]
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                module = node.module or "" if isinstance(node, ast.ImportFrom) else alias.name
                if (isinstance(node, ast.ImportFrom) and node.level) or not any(
                    module == allowed or module.startswith(allowed + ".")
                    for allowed in imports["allow"]
                ):
                    findings.add((imports["name"], node.lineno))
                full = f"{module}.{alias.name}" if isinstance(node, ast.ImportFrom) else alias.name
                local = alias.asname or (alias.name if isinstance(node, ast.ImportFrom)
                                         else alias.name.split(".")[0])
                aliases[(scope(node), local)] = full if alias.asname or isinstance(node, ast.ImportFrom) else local

    def qualified(node):
        if isinstance(node, ast.Name):
            return aliases.get((scope(node), node.id), aliases.get((tree, node.id), node.id))
        if isinstance(node, ast.Attribute):
            return f"{qualified(node.value)}.{node.attr}"
        return ""

    assignments = [n for n in ast.walk(tree) if isinstance(n, ast.Assign)]

    def expanded_nodes(node, before, seen=frozenset()):
        yield node
        if isinstance(node, ast.Name) and node.id not in seen:
            writes = [n for n in assignments if n.lineno < before and scope(n) is scope(node)
                      and any(isinstance(t, ast.Name) and t.id == node.id for t in n.targets)]
            if writes:
                last = max(writes, key=lambda n: n.lineno)
                yield from expanded_nodes(last.value, last.lineno, seen | {node.id})
        for child in ast.iter_child_nodes(node):
            yield from expanded_nodes(child, before, seen)

    def depends(node, names, before):
        return any(isinstance(n, ast.Name) and n.id in names
                   for n in expanded_nodes(node, before))

    for rule in config.get("rules", []):
        kind = rule["kind"]
        if kind == "for_over_axis":
            for node in ast.walk(tree):
                if isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
                    line = getattr(node, "lineno", getattr(node.target, "lineno", 1))
                    if depends(node.iter, rule["arrays"], line):
                        findings.add((rule["name"], line))
        elif kind == "call_on_unshifted_input":
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or qualified(node.func) not in rule["calls"]:
                    continue
                args = node.args + [kw.value for kw in node.keywords]
                for arg in args:
                    if not depends(arg, rule["inputs"], node.lineno):
                        continue
                    shifted = any(
                        isinstance(n, ast.BinOp) and isinstance(n.op, ast.Sub)
                        and depends(n.left, rule["inputs"], node.lineno)
                        and any(isinstance(r, ast.Call)
                                and (qualified(r.func) in rule["reductions"]
                                     or isinstance(r.func, ast.Attribute)
                                     and r.func.attr in rule.get("reduction_methods", []))
                                and depends(r, rule["inputs"], node.lineno)
                                for r in expanded_nodes(n.right, node.lineno))
                        for n in expanded_nodes(arg, node.lineno)
                    )
                    if not shifted:
                        findings.add((rule["name"], node.lineno))
        elif kind in ("required_node", "banned_node"):
            matches = [n for n in ast.walk(tree) if type(n).__name__ in rule["nodes"]]
            if kind == "required_node" and not matches:
                function = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)), tree)
                findings.add((rule["name"], getattr(function, "lineno", 1)))
            elif kind == "banned_node":
                findings.update((rule["name"], getattr(n, "lineno", 1)) for n in matches)
        else:
            raise ValueError(f"Unknown static rule kind: {kind}")
    return {"syntax_error": None,
            "findings": [{"name": name, "line": line} for name, line in sorted(findings, key=lambda x: (x[1], x[0]))]}
