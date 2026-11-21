"""Write workers/<name>/worker.py from heads/<name>.py plus the shared contract block.

Usage, after editing either part:
    python3 workers/_template/build.py && (cd workers && uvx ruff check --fix . && uvx ruff format .)
"""

from pathlib import Path

HERE = Path(__file__).resolve().parent
BLOCK = (HERE / "contract_block.py").read_text(encoding="utf-8")

for head in sorted((HERE / "heads").glob("*.py")):
    text = head.read_text(encoding="utf-8")
    docstring_end = text.index('"""', 3) + 3
    docstring, body = text[:docstring_end], text[docstring_end:]
    imports, rest = BLOCK.split("RESULT_FILE", 1)
    worker = f"{docstring}\n\n{imports.rstrip()}\n{body.strip()}\n\n\nRESULT_FILE{rest}"
    target = HERE.parent / head.stem / "worker.py"
    target.write_text(worker, encoding="utf-8")
    print("wrote", target.relative_to(HERE.parent.parent))
