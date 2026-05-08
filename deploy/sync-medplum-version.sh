#!/usr/bin/env bash
set -euo pipefail

source deploy/versions.sh

python3 - <<'PY'
import json
import re
from pathlib import Path

versions = {}
for line in Path("deploy/versions.sh").read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    versions[key] = value.strip().strip('"').strip("'")

medplum_version = versions["MEDPLUM_VERSION"]
provider_version = versions.get("MEDPLUM_PROVIDER_VERSION", medplum_version)
provider_image_tag = versions.get("MEDPLUM_PROVIDER_IMAGE_TAG", provider_version)

chart_path = Path("deploy/charts/medplum/Chart.yaml")
chart_text = chart_path.read_text()
chart_text = re.sub(
    r'(- name: medplum\s+version: )"[^"]+"',
    rf'\1"{medplum_version}"',
    chart_text,
)
chart_path.write_text(chart_text)

values_path = Path("deploy/charts/medplum/values-medplum.yaml")
values_text = values_path.read_text()
values_text = re.sub(r'medplumVersion: "[^"]+"', f'medplumVersion: "{medplum_version}"', values_text)
values_text = re.sub(
    r'medplumProviderVersion: "[^"]+"',
    f'medplumProviderVersion: "{provider_version}"',
    values_text,
)
values_text = re.sub(
    r'medplumProviderImageTag: "[^"]+"',
    f'medplumProviderImageTag: "{provider_image_tag}"',
    values_text,
)
values_text = re.sub(
    r'(\n\s+image:\n\s+repository: medplum/medplum-server\n\s+tag: )"[^"]+"',
    rf'\1"{medplum_version}"',
    values_text,
)
values_path.write_text(values_text)

package_path = Path("apps/medplum-provider/package.json")
package = json.loads(package_path.read_text())
package["version"] = provider_version
for name in list(package.get("devDependencies", {})):
    if name.startswith("@medplum/"):
        package["devDependencies"][name] = provider_version
package_path.write_text(json.dumps(package, indent=2) + "\n")
PY

echo "Synced Medplum chart/app to ${MEDPLUM_VERSION}"
echo "Synced Medplum Provider package/image to ${MEDPLUM_PROVIDER_VERSION}/${MEDPLUM_PROVIDER_IMAGE_TAG}"
echo "Run: helm dependency update deploy/charts/medplum"
