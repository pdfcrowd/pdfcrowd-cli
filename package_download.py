"""Build the source download from the same independently buildable inputs."""

import json
from pathlib import Path
import zipfile

root = Path(__file__).resolve().parent
version = json.loads((root / 'release.json').read_text())['version']
name = f'pdfcrowd-{version}-cli'
destination = root / 'dist' / f'{name}.zip'
excluded = {'dist', 'build', '.git', '__pycache__'}
with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        if (path.is_file() and not any(part in excluded or
                part.endswith('.egg-info') for part in relative.parts)):
            archive.write(path, Path(name) / relative)
