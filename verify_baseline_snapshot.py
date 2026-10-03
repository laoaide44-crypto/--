import hashlib, os, io, re

dst = '_freeze-20261001-prestart'
man = io.open(os.path.join(dst, 'MANIFEST.md'), encoding='utf-8').read()
rows = re.findall(r'^\| (.+?) \| (\d+) \| ([0-9a-f]{64}) \|', man, re.M)
ok = bad = 0
badlist = []
listed = set()
for name, size, h in rows:
    listed.add(name.replace('/', os.sep))
    p = os.path.join(dst, name)
    if not os.path.exists(p):
        bad += 1
        badlist.append((name, 'missing'))
        continue
    real = hashlib.sha256(open(p, 'rb').read()).hexdigest()
    if real == h and int(size) == os.path.getsize(p):
        ok += 1
    else:
        bad += 1
        badlist.append((name, 'hash/size mismatch'))

# extra files in snapshot not in manifest
extras = []
for dirpath, _, files in os.walk(dst):
    for f in files:
        rel = os.path.relpath(os.path.join(dirpath, f), dst)
        if rel.replace('/', os.sep) not in listed and rel != 'MANIFEST.md':
            extras.append(rel)

print('manifest rows:', len(rows))
print('verified OK:', ok, '| BAD:', bad)
print('badlist:', badlist)
print('unlisted extras:', extras)
print('RESULT:', 'ALL GOOD' if (bad == 0 and not extras) else 'PROBLEM')
