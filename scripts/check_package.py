"""Check exact public payload coverage and hashes; not a scientific validator."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / 'MANIFEST.json').read_text())
seen = set()
for item in manifest['files']:
    name = item['path']
    p = root / name
    if name in seen or not p.resolve().is_relative_to(root) or not p.is_file():
        raise ValueError('Unsafe, duplicate or missing manifest path: ' + name)
    seen.add(name)
    if p.stat().st_size != item['size_bytes'] or hashlib.sha256(p.read_bytes()).hexdigest() != item['sha256']:
        raise ValueError('Byte mismatch: ' + name)
actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()
          and '.git' not in p.relative_to(root).parts and '__pycache__' not in p.parts}
if actual != seen | {'MANIFEST.json'}:
    raise ValueError('Unexpected manifest inventory: ' + repr(actual ^ (seen | {'MANIFEST.json'})))
print('All', len(seen), 'public payload files match manifest; no unexpected files.')
