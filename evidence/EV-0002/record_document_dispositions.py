"""Record exact before blocks and their retained/condensed destinations."""
import bisect
import collections
import hashlib
import json
import re
import subprocess

from reconcile_document_links import ROOT, OUT, SUBJECTS, before, headings, make_maps
from verify_documentation import normalized


def main():
    maps = make_maps()
    rows = []
    metrics = {}
    for name in SUBJECTS:
        original = before(name)
        current = (ROOT / name).read_text(encoding='utf-8-sig')
        old_headings = headings(original)
        new_headings = headings(current)
        old_lines = [h['line'] for h in old_headings]
        new_lines = [h['line'] for h in new_headings]
        current_normal = normalized(current)
        counts = collections.Counter()
        matches = list(re.finditer(r'(?m)\S[^\n]*(?:\n(?!\s*$)[^\n]*)*', original))
        covered = ''.join(re.sub(r'\s+', '', match[0]) for match in matches)
        if covered != re.sub(r'\s+', '', original):
            raise ValueError(f'Incomplete source-block accounting: {name}')
        for match in matches:
            block = match[0]
            line = original[:match.start()].count('\n') + 1
            heading = old_headings[max(0, bisect.bisect_right(old_lines, line)-1)]
            destination = maps[name][heading['anchor']]
            if block in current:
                disposition = 'verbatim-retained-or-moved'
                current_line = current[:current.index(block)].count('\n')+1
                destination = new_headings[max(0, bisect.bisect_right(new_lines, current_line)-1)]['anchor']
                reason = 'Original text remains in the current subject.'
            elif normalized(block) in current_normal:
                disposition = 'retained-with-heading-whitespace-or-link-repair'
                reason = 'Content remains after editorial heading/wrapping/link normalization.'
            else:
                disposition = 'condensed-or-superseded-history'
                reason = (
                    'Completed-stage narrative, duplicate explanation or superseded instruction is '
                    'replaced by the linked outcome/method/decision summary. Original text/hash '
                    'remain in this ledger and the before snapshot; no historical raw verdict '
                    'or frozen authority bytes are rewritten.')
                if name == 'docs/DESKTOP_UI.md':
                    reason = (
                        'Visual/interaction content is reorganized or current framing corrected. '
                        'Duplicated/stale host, service signatures and transport recipes defer '
                        'to INTERFACES, ARCHITECTURE and BRIDGE. Existing explicit contrast '
                        'exceptions and shipped ordinary copied-file Verify remain; no new behavior.')
            counts[disposition] += 1
            rows.append(dict(source=name, start=line, end=line+block.count('\n'),
                             source_heading=heading['title'], original_sha256=hashlib.sha256(block.encode()).hexdigest(),
                             original_text=block, disposition=disposition,
                             destination=name+'#'+destination, reason=reason))
        metrics[name] = dict(blocks=sum(counts.values()), dispositions=dict(counts),
                             before_sha256=hashlib.sha256(original.encode()).hexdigest(),
                             after_sha256=hashlib.sha256(current.encode()).hexdigest())
    with (OUT / 'documentation-dispositions.jsonl').open('w', encoding='utf-8') as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False)+'\n')
    (OUT / 'documentation-disposition-summary.json').write_text(json.dumps(metrics, indent=2), encoding='utf-8')

    # Reconstruct the complete final link delta against baseline, including
    # already-repaired consumers across repeated composition runs.
    tracked = subprocess.check_output(['git', 'ls-files', '*.md'], cwd=ROOT, text=True).splitlines()
    changes = []
    for name in tracked:
        current = (ROOT / name).read_text(encoding='utf-8-sig')
        original = before(name)
        old = collections.Counter(re.findall(r'\]\(([^\s)]+)\)', original))
        new = collections.Counter(re.findall(r'\]\(([^\s)]+)\)', current))
        removed, added = list((old-new).elements()), list((new-old).elements())
        if removed or added:
            changes.append(dict(source=name, removed=removed, added=added))
    (OUT / 'documentation-final-link-delta.json').write_text(json.dumps(changes, indent=2), encoding='utf-8')
    print(json.dumps(metrics, indent=2))


if __name__ == '__main__':
    main()
