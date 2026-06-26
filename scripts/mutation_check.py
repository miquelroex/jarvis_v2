"""
mutation_check.py — Mini mutation-tester por AST (Windows + Python 3.13 friendly).

Las herramientas estándar (mutmut, mutatest) no funcionan en Windows/3.13, así que
esta es una alternativa ligera y autocontenida para medir la FUERZA de los tests.

Aplica, de una en una, mutaciones a un módulo (invierte comparaciones, and/or y
booleanos), reescribe el fichero temporalmente, ejecuta su test y observa:
  - test FALLA  -> mutante "muerto"  (bien: tus tests lo cazan)
  - test PASA   -> mutante "vivo"    (hueco: el cambio pasó desapercibido)

El fichero original SIEMPRE se restaura (try/finally + copia de seguridad).

Uso:
    python scripts/mutation_check.py core/voice_tone.py tests/test_voice_tone.py
"""
import ast
import sys
import copy
import subprocess
from pathlib import Path

_OPP = {
    ast.Eq: ast.NotEq, ast.NotEq: ast.Eq,
    ast.Lt: ast.GtE, ast.GtE: ast.Lt,
    ast.Gt: ast.LtE, ast.LtE: ast.Gt,
}


class _Tagger(ast.NodeVisitor):
    """Asigna un id único a cada nodo mutable."""
    def __init__(self):
        self.count = 0

    def _tag(self, node):
        node._mid = self.count
        self.count += 1

    def visit_Compare(self, node):
        if all(type(op) in _OPP for op in node.ops):
            self._tag(node)
        self.generic_visit(node)

    def visit_BoolOp(self, node):
        self._tag(node)
        self.generic_visit(node)

    def visit_Constant(self, node):
        if isinstance(node.value, bool):
            self._tag(node)


class _Mutator(ast.NodeTransformer):
    def __init__(self, target):
        self.target = target
        self.desc = None

    def visit_Compare(self, node):
        if getattr(node, "_mid", None) == self.target:
            node.ops = [_OPP.get(type(op), type(op))() for op in node.ops]
            self.desc = f"comparacion invertida (linea {node.lineno})"
        return self.generic_visit(node)

    def visit_BoolOp(self, node):
        if getattr(node, "_mid", None) == self.target:
            node.op = ast.Or() if isinstance(node.op, ast.And) else ast.And()
            self.desc = f"and/or invertido (linea {node.lineno})"
        return self.generic_visit(node)

    def visit_Constant(self, node):
        if getattr(node, "_mid", None) == self.target and isinstance(node.value, bool):
            node.value = not node.value
            self.desc = f"booleano invertido (linea {node.lineno})"
        return node


def _run_test(test_file: str) -> bool:
    """True si el test PASA (mutante vivo)."""
    res = subprocess.run([sys.executable, "-m", "pytest", test_file, "-q"],
                         capture_output=True, text=True)
    return res.returncode == 0


def main(module: str, test_file: str):
    path = Path(module)
    original_bytes = path.read_bytes()           # para restaurar EXACTO (bytes/newlines)
    tree = ast.parse(original_bytes.decode("utf-8"))
    tagger = _Tagger()
    tagger.visit(tree)
    total = tagger.count
    print(f"Mutantes a probar en {module}: {total}\n")

    killed, survived, invalid = 0, 0, 0
    survivors = []
    try:
        for target in range(total):
            mutant_tree = copy.deepcopy(tree)
            mut = _Mutator(target)
            mut.visit(mutant_tree)
            ast.fix_missing_locations(mutant_tree)
            try:
                mutant_src = ast.unparse(mutant_tree)
            except Exception:
                invalid += 1
                continue
            path.write_text(mutant_src, encoding="utf-8")
            alive = _run_test(test_file)
            if alive:
                survived += 1
                survivors.append(mut.desc or f"mutante {target}")
                print(f"  [VIVO]   #{target}: {mut.desc}")
            else:
                killed += 1
                print(f"  [muerto] #{target}: {mut.desc}")
    finally:
        path.write_bytes(original_bytes)  # restaurar EXACTO, SIEMPRE

    scored = killed + survived
    score = (killed / scored * 100) if scored else 100.0
    print(f"\n=== Mutation score: {score:.0f}%  ({killed} muertos / {scored}) ===")
    if survivors:
        print("Mutantes vivos (huecos de test):")
        for s in survivors:
            print(f"  - {s}")
    return score


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso: python scripts/mutation_check.py <modulo.py> <test_file.py>")
        sys.exit(2)
    main(sys.argv[1], sys.argv[2])
