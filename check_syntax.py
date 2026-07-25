"""Standalone script: check Python syntax of backend/ and graph-rag/ recursively."""
import os
import sys
import ast

base = sys.argv[1] if len(sys.argv) > 1 else "backend"
errors = []
count = 0
for root, _dirs, files in os.walk(base):
    # skip node_modules
    if "node_modules" in root:
        continue
    for fname in files:
        if not fname.endswith(".py"):
            continue
        fpath = os.path.join(root, fname)
        count += 1
        try:
            with open(fpath, "r", encoding="utf-8") as fh:
                ast.parse(fh.read(), filename=fpath)
        except UnicodeDecodeError:
            with open(fpath, "rb") as fh:
                raw = fh.read()
            for enc in ("utf-8", "latin-1", "cp1252"):
                try:
                    ast.parse(raw.decode(enc), filename=fpath)
                    break
                except (UnicodeDecodeError, SyntaxError) as ex:
                    if isinstance(ex, SyntaxError):
                        errors.append(f"{fpath}: {ex}")
                        break
            else:
                errors.append(f"{fpath}: decode failed (binary or weird encoding)")
        except SyntaxError as ex:
            errors.append(f"{fpath}: {ex}")

print(f"Checked {count} .py files under {base}/")
if errors:
    print(f"\n{len(errors)} SYNTAX ERROR(S):")
    for e in errors:
        print(f"  ERR: {e}")
    sys.exit(1)
else:
    print("  ALL OK — zero syntax errors.")