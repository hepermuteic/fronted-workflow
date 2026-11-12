"""Export a clean installable folder and ZIP from the Skill allowlist."""
import argparse
import json
from pathlib import Path
import shutil
import zipfile

from install import PACKAGE, package_files


def build(output):
    output = Path(output).resolve()
    folder = output / 'frontend-workflow'
    archive = output / 'frontend-workflow.zip'
    if folder.exists() or archive.exists():
        raise ValueError('Choose an unused output directory to preserve existing packages')
    contents = list(package_files(PACKAGE))
    folder.mkdir(parents=True)
    for source, relative in contents:
        target = folder / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as stream:
        for _, relative in contents:
            stream.write(folder / relative, str(Path('frontend-workflow') / relative))
    return {'folder': str(folder), 'zip': str(archive), 'files': len(contents), 'zip_bytes': archive.stat().st_size}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    print(json.dumps(build(parser.parse_args().output), ensure_ascii=False, indent=2))
