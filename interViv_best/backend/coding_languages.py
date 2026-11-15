"""Language templates and judge drivers. Expected answers stay in the API process."""
from __future__ import annotations

import ast
import json
import re
from typing import Any

LANGUAGES = {
    "python": {"label": "Python 3.12", "runtime": "python", "version": "3.12.0", "editor": "python"},
    "javascript": {"label": "JavaScript (Node 20)", "runtime": "javascript", "version": "20.11.1", "editor": "javascript"},
    "java": {"label": "Java 15", "runtime": "java", "version": "15.0.2", "editor": "java"},
    "cpp": {"label": "C++17 (GCC 10)", "runtime": "c++", "version": "10.2.0", "editor": "cpp"},
}


def normalize_language(language: str | None) -> str:
    value = str(language or "python").strip().lower()
    if value not in LANGUAGES:
        raise ValueError("Choose Python, JavaScript, Java or C++.")
    return value


def _type(values: list[Any]) -> str:
    sample = next((v for v in values if v != []), values[0] if values else 0)
    if isinstance(sample, list):
        flattened = [item for value in values if isinstance(value, list) for item in value]
        return "list[" + _type(flattened) + "]"
    if isinstance(sample, bool):
        return "bool"
    if isinstance(sample, str):
        return "str"
    if any(isinstance(value, float) for value in values):
        return "float"
    return "int"


def signature(problem: dict) -> tuple[list[tuple[str, str]], str]:
    """Infer a typed interface from trusted starter and public examples only."""
    tree = ast.parse(problem["starter_code"])
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef))
    examples = problem["visible_tests"]
    params = [(arg.arg, _type([case["input"]["args"][i] for case in examples]))
              for i, arg in enumerate(function.args.args)]
    return params, _type([case["expected"] for case in examples])


def _typename(kind: str, language: str) -> str:
    if kind.startswith("list["):
        inner = _typename(kind[5:-1], language)
        return inner + "[]" if language == "java" else "vector<" + inner + ">"
    return {"java": {"int": "int", "float": "double", "str": "String", "bool": "boolean"},
            "cpp": {"int": "int", "float": "double", "str": "string", "bool": "bool"}}[language][kind]


def starter_codes(problem: dict) -> dict[str, str]:
    params, result = signature(problem)
    name = problem["function"]
    names = ", ".join(p[0] for p in params)
    java_args = ", ".join(f"{_typename(t, 'java')} {n}" for n, t in params)
    cpp_args = ", ".join(f"{_typename(t, 'cpp')} {n}" for n, t in params)
    return {
        "python": problem["starter_code"],
        "javascript": f"function {name}({names}) {{\n  // Write your solution here.\n  throw new Error('Not implemented');\n}}\n",
        "java": f"import java.util.*;\n\nclass Solution {{\n    public {_typename(result, 'java')} {name}({java_args}) {{\n        // Write your solution here.\n        throw new UnsupportedOperationException(\"Not implemented\");\n    }}\n}}\n",
        "cpp": f"#include <bits/stdc++.h>\nusing namespace std;\n\nclass Solution {{\npublic:\n    {_typename(result, 'cpp')} {name}({cpp_args}) {{\n        // Write your solution here.\n        throw runtime_error(\"Not implemented\");\n    }}\n}};\n",
    }


def _literal(value: Any, kind: str, language: str) -> str:
    if kind.startswith("list["):
        values = ",".join(_literal(v, kind[5:-1], language) for v in value)
        prefix = "new " + _typename(kind, language) if language == "java" else _typename(kind, language)
        return prefix + "{" + values + "}"
    if kind == "str":
        if language == "java":
            codes = ",".join(str(ord(c)) for c in value)
            return f"new String(new int[]{{{codes}}},0,{len(value)})"
        codes = ",".join(f"char({c})" for c in value.encode("utf-8"))
        return f"string({{{codes}}})"
    if kind == "bool":
        return "true" if value else "false"
    return json.dumps(value, allow_nan=False)


CPP_JSON = r'''
#include <bits/stdc++.h>
using namespace std;
namespace interviv {
void emit(const string& s) {
    cout << '"';
    for (unsigned char c : s) {
        if (c == '"' || c == '\\') cout << '\\' << c;
        else if (c < 32) cout << "\\u00" << hex << setw(2) << setfill('0') << int(c) << dec;
        else cout << c;
    }
    cout << '"';
}
void emit(bool v) { cout << (v ? "true" : "false"); }
template<class T> void emit(const vector<T>&);
template<class T> void emit(const T& v) { cout << setprecision(17) << v; }
template<class T> void emit(const vector<T>& values) {
    cout << '[';
    for (size_t i=0; i<values.size(); ++i) { if(i) cout << ','; emit(values[i]); }
    cout << ']';
}
}
'''

JAVA_JSON = r'''
static String json(Object value) {
    if(value == null) return "null";
    if(value instanceof String) {
        StringBuilder b = new StringBuilder("\"");
        for(char c: ((String)value).toCharArray()) {
            if(c == '"' || c == '\\') b.append('\\').append(c);
            else if(c < 32) b.append(String.format("\\u%04x", (int)c));
            else b.append(c);
        }
        return b.append('"').toString();
    }
    if(value.getClass().isArray()) {
        StringBuilder b = new StringBuilder("[");
        int n = java.lang.reflect.Array.getLength(value);
        for(int i=0;i<n;i++) { if(i>0)b.append(','); b.append(json(java.lang.reflect.Array.get(value,i))); }
        return b.append(']').toString();
    }
    if(value instanceof Number || value instanceof Boolean) return value.toString();
    throw new IllegalArgumentException("Return the type declared in the starter.");
}
'''


# Java's Piston runtime launches a single source file directly. Keep legal
# package/import declarations ahead of our harness, then append the user's
# classes to that same file so the source-file launcher can resolve Solution.
_JAVA_PREAMBLE = re.compile(
    r"\A(?:(?:\s+|//[^\n]*(?:\n|$)|/\*.*?\*/)|"
    r"(?:(?:package|import)\s+(?:static\s+)?[\w.$*]+\s*;))*",
    re.DOTALL,
)


def build_driver(*, source: str, function: str, tests: list[dict], language: str,
                 marker: str, problem: dict | None = None) -> list[dict[str, str]]:
    """Build code for Piston, never execute candidate code in the host process."""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", function):
        raise ValueError("Invalid problem function.")
    inputs = [case["input"]["args"] for case in tests]
    if language == "python":
        # Syntax validation does not execute candidate code.
        ast.parse(source)
        driver = (
            "import json, importlib.util\n"
            "spec=importlib.util.spec_from_file_location('solution','solution.py')\n"
            "solution=importlib.util.module_from_spec(spec)\nspec.loader.exec_module(solution)\n"
            f"cases=json.loads({json.dumps(json.dumps(inputs, ensure_ascii=True))})\n"
            "for i,args in enumerate(cases):\n"
            "    try:\n"
            f"        value=getattr(solution,{function!r})(*args)\n"
            "        result={'i':i,'value':value}\n"
            "    except Exception as exc:\n"
            "        result={'i':i,'error':'runtime','message':type(exc).__name__+': '+str(exc)[:500]}\n"
            f"    print({marker!r}+json.dumps(result,allow_nan=False),flush=True)\n"
        )
        return [{"name": "main.py", "content": driver}, {"name": "solution.py", "content": source}]
    if language == "javascript":
        driver = source + "\n;\n" + (
            f"const __cases={json.dumps(inputs, ensure_ascii=True)};\n"
            "for(let i=0;i<__cases.length;i++){\n"
            f"try{{console.log({json.dumps(marker)}+JSON.stringify({{i,value:{function}(...__cases[i])}}));}}\n"
            f"catch(e){{console.log({json.dumps(marker)}+JSON.stringify({{i,error:'runtime',message:String(e).slice(0,500)}}));}}\n"
            "}\n"
        )
        return [{"name": "main.js", "content": driver}]
    if problem is None:
        raise ValueError("Typed languages require a problem interface.")
    params, _ = signature(problem)
    calls = []
    for index, args in enumerate(inputs):
        values = ",".join(_literal(v, kind, language) for v, (_, kind) in zip(args, params))
        prefix = json.dumps(marker + '{"i":' + str(index) + ',"value":')
        error = json.dumps(marker + '{"i":' + str(index) + ',"error":"runtime"}')
        if language == "java":
            calls.append(f'try {{ System.out.println({prefix}+json(new Solution().{function}({values}))+"}}"); }} catch(Throwable e) {{ System.out.println({error}); }}')
        else:
            calls.append(f'try {{ auto value=Solution().{function}({values}); cout << {prefix}; interviv::emit(value); cout << "}}" << endl; }} catch(...) {{ cout << {error} << endl; }}')
    if language == "java":
        match = _JAVA_PREAMBLE.match(source)
        prefix = match.group(0) if match else ""
        solution = source[len(prefix):]
        driver = (prefix + "\nclass InterVivMain {\n" + JAVA_JSON
                  + "\npublic static void main(String[] args) {\n"
                  + "\n".join(calls) + "\n}}\n" + solution)
        # This runtime adds .java itself; do not include it in the file name.
        return [{"name": "InterVivMain", "content": driver}]
    return [{"name": "main.cpp", "content": CPP_JSON + "\n" + source + "\nint main(){\n" + "\n".join(calls) + "\n}\n"}]
