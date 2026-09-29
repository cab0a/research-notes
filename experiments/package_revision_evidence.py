"""Package fixed STEP examples and notices without changing upstream bytes."""
from pathlib import Path
import hashlib
import json
import zipfile

from research_notes.revision_benchmark import verified_assets

ROOT = Path(__file__).resolve().parents[1]


def main():
    corpus = ROOT / 'fixtures/revision-comparison'
    manifest, _ = verified_assets(corpus)
    paths = {corpus / 'manifest.json', corpus / 'README.md', ROOT / 'LICENSE'}
    paths.update((corpus / name).resolve() for name in manifest['assets'])
    public = ROOT / 'fixtures/public-step-corpus'
    paths.update([public / 'manifest.json', public / 'README.md'])
    paths.update(p for p in (public / 'licenses').rglob('*') if p.is_file())
    output = ROOT / 'results/revision-benchmark/samples.zip'
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(paths):
            name = path.relative_to(ROOT).as_posix()
            info = zipfile.ZipInfo(name, date_time=(2026, 9, 29, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
        info = zipfile.ZipInfo('README.txt', date_time=(2026, 9, 29, 0, 0, 0))
        archive.writestr(info, 'Research CAD v1.7.0 fixed STEP examples\n'
            'Source: https://github.com/cab0a/research-notes\n'
            'Install the matching source revision and its geometry extra.\n'
            'From the extracted directory run:\n'
            'python -m research_notes.revision_benchmark --corpus-dir fixtures/revision-comparison --output-dir output/check\n'
            'Authored controls: LICENSE (PolyForm Noncommercial 1.0.0).\n'
            'External inputs: separate upstream terms and notices in fixtures/public-step-corpus/licenses.\n'
            'External self-pairs test intake only, not real manufacturer design revisions.\n')
    record = {'archive': output.name, 'sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
              'bytes': output.stat().st_size, 'fixed_step_files': len(manifest['assets']),
              'case_count': len(manifest['cases']), 'upstream_bytes_modified': False}
    (output.parent / 'bundle.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    main()
