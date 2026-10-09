#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
import copy
import io
import os
import re
import tarfile
import tempfile
from pathlib import Path

archive = Path("deploy/charts/medplum/charts/medplum-" + re.search(
    r'  - name: medplum\n    version: "([^"]+)"',
    Path("deploy/charts/medplum/Chart.yaml").read_text(),
).group(1) + ".tgz")
target = "medplum/templates/deployment.yaml"
replacements = {
    b"{{- if (eq .Values.global.cloudProvider \"azure\") }}":
        b"{{ if (eq .Values.global.cloudProvider \"azure\") }}",
    b"{{- toYaml . | nindent 6 }}":
        b"{{- toYaml . | nindent 12 }}",
}

with tarfile.open(archive, "r:gz") as source:
    members = source.getmembers()
    files = {member.name: source.extractfile(member).read()
             for member in members if member.isfile()}

if target not in files:
    raise SystemExit(f"Missing {target} in {archive}")
for old, new in replacements.items():
    count = files[target].count(old)
    if count:
        files[target] = files[target].replace(old, new)
    elif new not in files[target]:
        raise SystemExit(f"Expected template fragment in {target}: {old.decode()}")

fd, temporary_name = tempfile.mkstemp(dir=archive.parent, suffix=".tgz")
os.close(fd)
try:
    with tarfile.open(temporary_name, "w:gz") as destination:
        for member in members:
            info = copy.copy(member)
            if member.isfile():
                data = files[member.name]
                info.size = len(data)
                destination.addfile(info, io.BytesIO(data))
            else:
                destination.addfile(info)
    os.replace(temporary_name, archive)
except Exception:
    os.unlink(temporary_name)
    raise

print(f"Patched whitespace bug in {archive}:{target}")
PY
