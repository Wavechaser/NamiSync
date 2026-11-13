"""Verify the follow-up UI delta and account for each original prose block."""
import bisect
import hashlib
import json
import re

from reconcile_document_links import ROOT, OUT, headings, slug
from verify_documentation import normalized

source = (OUT / 'ui-round2-before.txt').read_text(encoding='utf-8-sig')
current = (ROOT / 'docs/DESKTOP_UI.md').read_text(encoding='utf-8-sig')
original_headings = headings(source)
current_headings = headings(current)
current_anchors = {h['anchor'] for h in current_headings}
mapping = {
    'purpose': 'scope-and-owners', 'scope-and-delivery-boundary': 'scope-and-owners',
    'packaging-and-local-host-state': 'host-and-security-boundary',
    'semantic-color-channels': 'palette-and-semantic-channels',
    'command-controls-and-fills': 'control-fills-borders-and-focus',
    'textboxes-and-combobox-triggers': 'control-fills-borders-and-focus',
    'focus-checkboxes-and-switches': 'control-fills-borders-and-focus',
    'elevated-surfaces-and-advanced-color': 'surfaces-appearance-and-motion',
    'file-row-components': 'file-row-components-and-geometry',
    'icon-vocabulary': 'app-icon-and-glyph-vocabulary', 'app-icon': 'app-icon-and-glyph-vocabulary',
    'appearance-selector-and-material-lifecycle': 'surfaces-appearance-and-motion',
    'motion': 'surfaces-appearance-and-motion', 'adapter-boundary': 'host-and-security-boundary',
    'bridge-and-renderer-security': 'host-and-security-boundary',
    'folder-admission-and-pending-starts': 'setup-and-location-flow',
    'recent-pairs-and-batch-composition': 'recent-pairs-and-batches',
    'task-creation-and-empty-shell': 'shell-layout-and-settings',
    'sorting-and-automatic-follow': 'sorting-and-automatic-follow',
    'highlighting-and-execution-selection': 'highlighting-details-and-confirmation',
    'item-details-and-full-paths': 'highlighting-details-and-confirmation',
    'defaults-and-about': 'shell-layout-and-settings', 'task-rail-and-status-cards': 'shell-layout-and-settings',
    'task-lifetime-and-close': 'close-and-uncertain-outcomes',
    'capacity-refusal-and-retained-review': 'execution-admission-and-plan-again',
    'inventory-toolbar-and-progress': 'inventory-controls-and-details',
    'inventory-details': 'inventory-controls-and-details',
    'ordinary-integrity-actions': 'integrity-operation-semantics',
    'deferred-history': 'presentation-and-responsiveness',
}
for heading in original_headings:
    anchor = heading['anchor']
    target = anchor if anchor in current_anchors else mapping.get(anchor)
    if target not in current_anchors:
        raise ValueError(('Unmapped source section', heading))
    mapping[anchor] = target
rows = []
old_lines = [h['line'] for h in original_headings]
matches = list(re.finditer(r'(?m)\S[^\n]*(?:\n(?!\s*$)[^\n]*)*', source))
if ''.join(re.sub(r'\s+', '', m[0]) for m in matches) != re.sub(r'\s+', '', source):
    raise ValueError('Incomplete source accounting')
current_normal = normalized(current)
for match in matches:
    line = source[:match.start()].count('\n')+1
    owner = original_headings[max(0, bisect.bisect_right(old_lines, line)-1)]
    block = match[0]
    rows.append(dict(line=line, original_text=block, original_sha256=hashlib.sha256(block.encode()).hexdigest(),
                     source_heading=owner['title'], destination='docs/DESKTOP_UI.md#'+mapping[owner['anchor']],
                     disposition='retained-or-moved' if normalized(block) in current_normal else
                         'condensed-behavior-or-delegated-duplicate-source/test/projection/transport-detail'))
with (OUT / 'ui-round2-dispositions.jsonl').open('w', encoding='utf-8') as stream:
    for row in rows:
        stream.write(json.dumps(row, ensure_ascii=False)+'\n')
old_tables = re.findall(r'(?m)^\|[^\n]+(?:\n\|[^\n]+)+', source)
hexes = lambda t: set(re.findall(r'#[0-9A-Fa-f]{6,8}\b', t))
palette = lambda t: re.findall(r'--palette-[\w-]+:\s*#[0-9A-Fa-f]+;', t)
bugs_hash = json.loads((OUT / 'bugs-survey-hash.json').read_text(encoding='utf-8-sig'))['Hash']
bugs_unchanged = hashlib.sha256((ROOT / 'docs/BUGS.md').read_bytes()).hexdigest().upper() == bugs_hash
bug_report = json.loads((OUT / 'bugs-access-analysis.json').read_text())
receipt = dict(source_blocks_accounted=len(rows), source_sections_accounted=len(original_headings),
               specification_tables_unchanged=all(table in current for table in old_tables),
               color_literals_unchanged=hexes(source) == hexes(current),
               palette_unchanged=palette(source) == palette(current),
               acceptance_unchanged=source[source.index('## Acceptance criteria'):] == current[current.index('## Acceptance criteria'):],
               bugs_unchanged=bugs_unchanged, bug_record_coverage_complete=bug_report['header_coverage_complete'],
               bug_records=bug_report['entries'])
receipt['passed'] = all(receipt[key] for key in (
    'specification_tables_unchanged', 'color_literals_unchanged', 'palette_unchanged',
    'acceptance_unchanged', 'bugs_unchanged', 'bug_record_coverage_complete'))
(OUT / 'ui-round2-verification.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
print(json.dumps(receipt, indent=2))
if not receipt['passed']:
    raise SystemExit(1)
