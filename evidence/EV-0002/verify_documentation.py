"""Check the integrated editorial delta, preserved methods and link consumers."""
import collections
import hashlib
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote

from reconcile_document_links import ROOT, OUT, SUBJECTS, before, headings, make_maps


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def normalized(text):
    text = re.sub(r'\]\([^)]*\)', '](LINK)', text)
    text = re.sub(r'(?m)^#{1,6} ', '', text)
    return re.sub(r'\s+', ' ', text).strip()


def numbers(text):
    return re.findall(r'(?<![\w])[-+−]?\d[\d,.]*(?:/\d+)?(?![\w])', text)


def body_at(text, anchor):
    hs = headings(text)
    i = next(i for i, h in enumerate(hs) if h['anchor'] == anchor)
    end = hs[i+1]['line']-1 if i+1 < len(hs) else len(text.splitlines())
    return '\n'.join(text.splitlines()[hs[i]['line']:end])


def inline_links(text):
    fenced = False
    for number, line in enumerate(text.splitlines(), 1):
        if line.startswith(('```', '~~~')):
            fenced = not fenced
            continue
        if not fenced:
            for match in re.finditer(r'\]\(([^\s)]+)\)', line):
                yield number, match[1]


def check_links(tracked, texts):
    issues = []
    checked = 0
    for name in tracked:
        path = ROOT / name
        for line, dest in inline_links(texts[name]):
            raw_path, _, anchor = dest.partition('#')
            if re.match(r'^[a-zA-Z][\w+.-]*:', raw_path):
                continue
            target = (path.parent / unquote(raw_path)).resolve() if raw_path else path.resolve()
            checked += 1
            if not target.exists():
                issues.append(dict(source=name, line=line, destination=dest, reason='missing-path'))
                continue
            if anchor and target.suffix.lower() == '.md':
                try:
                    relative = target.relative_to(ROOT).as_posix()
                except ValueError:
                    continue
                target_text = texts.get(relative, target.read_text(encoding='utf-8-sig'))
                anchors = {h['anchor'] for h in headings(target_text)}
                anchors.update(re.findall(r'<a\s+(?:id|name)=["\']([^"\']+)', target_text))
                if unquote(anchor) not in anchors:
                    issues.append(dict(source=name, line=line, destination=dest, reason='missing-anchor'))
    return checked, issues


def main():
    tracked = subprocess.check_output(['git', 'ls-files', '*.md'], cwd=ROOT, text=True).splitlines()
    texts = {name: (ROOT / name).read_text(encoding='utf-8-sig') for name in tracked}
    old_texts = {name: before(name) for name in tracked}
    checked, issues = check_links(tracked, texts)
    _, old_issues = check_links(tracked, old_texts)
    key = lambda i: (i['source'], i['destination'], i['reason'])
    old_keys = {key(i) for i in old_issues}
    introduced = [i for i in issues if key(i) not in old_keys]
    affected = [i for i in issues if i['source'] in SUBJECTS + ['README.md', 'docs/HANDOFF.md']]

    methods = []
    perf = texts['docs/PERFORMANCE.md']
    original_perf = before('docs/PERFORMANCE.md')
    for item in json.loads((OUT / 'preserved-performance-ranges.json').read_text()):
        original = '\n'.join(original_perf.splitlines()[item['start']-1:item['end']]).strip()
        if item['edited']:
            anchor = headings(original)[0]['anchor']
            current = body_at(perf, anchor)
            original_body = '\n'.join(original.splitlines()[1:])
            ok = numbers(original_body) == numbers(current)
            kind = 'numeric-sequence-preserved; editorial delta separately reviewed'
        else:
            ok = normalized(original) in normalized(perf)
            kind = 'complete-text-preserved-except-heading-or-link-destination'
        methods.append(dict(fragment=item['fragment'], ok=ok, check=kind))

    ui_old = before('docs/DESKTOP_UI.md')
    ui_new = texts['docs/DESKTOP_UI.md']
    old_tables = re.findall(r'(?m)^\|[^\n]+(?:\n\|[^\n]+)+', ui_old)
    ui_tables = [table in ui_new for table in old_tables]
    palette = lambda t: re.findall(r'--palette-[\w-]+:\s*#[0-9A-Fa-f]+;', t)
    ui_palette = palette(ui_old) == palette(ui_new) and len(palette(ui_new)) == 15
    ui_old_gate = ui_old[ui_old.index('## Acceptance criteria'):]
    ui_new_gate = ui_new[ui_new.index('## Acceptance criteria'):]
    gate_count = lambda t: len(re.findall(r'(?m)^- ', t))
    expected_gate = ui_old_gate.replace(
        '  exact-handoff fallback labeling, and no browser-retained full result.',
        '  ordinary copied-file Verify with separate original/current results, and\n'
        '  no browser-retained full result.')
    ui_acceptance = expected_gate == ui_new_gate

    old_tasks = re.findall(r'(?m)^#### (.+)$', before('CHANGELOG.md'))
    new_tasks = re.findall(r'(?m)^#### (.+)$', texts['CHANGELOG.md'])
    tasks_preserved = collections.Counter(old_tasks) == collections.Counter(new_tasks)
    phase = None
    phase_dates = collections.defaultdict(list)
    for heading in headings(texts['CHANGELOG.md']):
        if heading['level'] == 3:
            phase = heading['title']
        elif heading['level'] == 4:
            phase_dates[phase].append(re.findall(r'\d{4}-\d{2}-\d{2}', heading['title'])[-1])
    newest_first = all(dates == sorted(dates, reverse=True) for dates in phase_dates.values())
    readme_phases = [h['title'] for h in headings(texts['README.md']) if h['level'] == 3 and h['title'].startswith(('M1 ', 'M0 '))]
    log_phases = list(phase_dates)
    metrics = {name: dict(before_lines=len(before(name).splitlines()),
                         after_lines=len(texts[name].splitlines()),
                         before_words=len(before(name).split()), after_words=len(texts[name].split()))
               for name in SUBJECTS}
    roots = sorted(set(re.findall(r'build/[A-Za-z0-9_.-]+', '\n'.join(texts[name] for name in SUBJECTS))))
    prior_roots = set(re.findall(r'build/[A-Za-z0-9_.-]+', '\n'.join(before(name) for name in SUBJECTS)))
    novel_roots = [dict(path=root, exists=(ROOT / root).exists()) for root in roots if root not in prior_roots]
    changed = subprocess.check_output(['git', 'diff', '--name-only'], cwd=ROOT, text=True).splitlines()
    result = dict(
        metrics=metrics, markdown_links_checked=checked, baseline_link_issues=old_issues,
        remaining_link_issues=issues, introduced_link_issues=introduced, subject_link_issues=affected,
        preserved_methods=methods, ui_tables_preserved=ui_tables, ui_palette_preserved=ui_palette,
        ui_acceptance_preserved_except_retired_exact_manual_label=ui_acceptance,
        ui_gate_count_before=gate_count(ui_old_gate), ui_gate_count_after=gate_count(ui_new_gate),
        changelog_tasks_preserved=tasks_preserved, changelog_task_count=len(new_tasks),
        newest_first=newest_first, readme_phase_alignment=readme_phases == log_phases,
        novel_evidence_roots=novel_roots, only_markdown_changed=all(p.endswith('.md') for p in changed))
    result['passed'] = (not introduced and not affected and all(m['ok'] for m in methods)
        and all(ui_tables) and ui_palette and ui_acceptance and tasks_preserved
        and newest_first and readme_phases == log_phases and result['only_markdown_changed']
        and all(item['exists'] for item in novel_roots))
    (OUT / 'documentation-verification.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(dict(passed=result['passed'], metrics=metrics,
        markdown_links_checked=checked, baseline_link_issues=len(old_issues),
        remaining_link_issues=len(issues), preserved_method_checks=len(methods),
        ui_tables_preserved=sum(ui_tables), ui_palette_preserved=ui_palette,
        ui_acceptance_preserved=ui_acceptance, changelog_tasks=len(new_tasks),
        newest_first=newest_first, readme_phase_alignment=readme_phases == log_phases,
        novel_evidence_roots=novel_roots, only_markdown_changed=result['only_markdown_changed']), indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
