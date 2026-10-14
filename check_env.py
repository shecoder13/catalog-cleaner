"""Environment check: imports the key libraries."""
import importlib
import sys

print(f"python {sys.version.split()[0]}")
ok = True
for mod in ["typer", "httpx", "anthropic"]:
    try:
        importlib.import_module(mod)
        print(f"  ok   {mod}")
    except Exception as e:
        ok = False
        print(f"  FAIL {mod}: {e}")
print("ENV OK" if ok else "ENV HAS PROBLEMS")
sys.exit(0 if ok else 1)
