"""Plot recorded counts, keeping the original regression and new limits separate."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, default=Path('results/hole-numerical-stability'))
    args = parser.parse_args()
    current = json.loads((args.results / 'results.json').read_text())
    comparison = json.loads((args.results / 'before-after.json').read_text())
    old = json.loads(Path('results/hole-robustness/results.json').read_text())
    new = json.loads((args.results / 'robustness/results.json').read_text())
    regression = next(r for r in comparison['records'] if r['path'] == 'step_scanners')
    groups = [
        ('Existing 1,000,000 mm offset model', ['v1.12', 'v1.13'],
         [regression['before_audit'], regression['after_audit']]),
        ('Existing 44 controls: unified STEP path', ['v1.12', 'v1.13'],
         [old['summary']['unified'], new['summary']['unified']]),
        ('12 additional extreme-coordinate controls', ['Native', 'STEP', 'Unified'],
         [current['summary'][k] for k in ('constructed', 'step_scanners', 'unified')]),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(15, 5.2), layout='constrained')
    for ax, (title, labels, values) in zip(axes, groups):
        matched = [v['matched_features'] for v in values]
        missed = [len(v['missed_truth_indices']) if 'missed_truth_indices' in v else v['missed_features'] for v in values]
        ax.bar(labels, matched, color='#237c68', label='Matched authored features')
        ax.bar(labels, missed, bottom=matched, color='#e4a45a', label='Withheld / missed features')
        for i, (m, n) in enumerate(zip(matched, missed)):
            ax.text(i, m+n+.35, f'{m}/{m+n} matched', ha='center', fontsize=10)
        ax.set_ylim(0, max(m+n for m, n in zip(matched, missed)) * 1.2 + 1)
        ax.set_title(title, fontsize=11)
        ax.set_ylabel('Authored eligible features')
        ax.spines[['top', 'right']].set_visible(False)
        ax.grid(axis='y', alpha=.2)
        ax.set_axisbelow(True)
    axes[0].legend(loc='upper left', fontsize=9)
    fig.suptitle('v1.13: material classification near each solid; unchanged qualification thresholds', fontsize=14)
    fig.supxlabel('Counts per input set; repeated outputs identical. Synthetic development controls, not population accuracy.', fontsize=10)
    fig.savefig(args.results / 'counts.png', dpi=140)
    plt.close(fig)


if __name__ == '__main__':
    main()
