"""Build and verify a deterministic licensed 21-input reproduction bundle."""
from pathlib import Path
import hashlib
import json
import zipfile

from research_notes.revision_benchmark import verified_assets

ROOT = Path(__file__).resolve().parents[1]


def main():
    corpus = ROOT / 'fixtures/hole-inventory'
    manifest, _ = verified_assets(corpus)
    paths = [ROOT/'LICENSE', ROOT/'LICENSING.md', corpus/'README.md', corpus/'manifest.json']
    paths += [(corpus/name).resolve() for name in manifest['assets']]
    public = ROOT/'fixtures/public-step-corpus'
    paths += [public/'README.md', public/'manifest.json']
    paths += [p for p in (public/'licenses').rglob('*') if p.is_file()]
    output = ROOT/'results/hole-inventory/samples.zip'
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(set(paths)):
            info = zipfile.ZipInfo(path.relative_to(ROOT).as_posix(), date_time=(2026, 9, 30, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    with zipfile.ZipFile(output) as archive:
        for path in sorted(set(paths)):
            assert archive.read(path.relative_to(ROOT).as_posix()) == path.read_bytes()
        assert len([name for name in archive.namelist() if name.endswith('.step')]) == 21
    print(json.dumps({'archive_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
                      'step_inputs': 21, 'members': len(set(paths))}, indent=2))


if __name__ == '__main__':
    main()
