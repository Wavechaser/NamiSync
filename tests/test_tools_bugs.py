from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys

import pytest

from tools.bugs import DEFAULT_SOURCE, load_records, main, parse_records


def _log(identity="0001", status="CLOSED, BOUNDED", date="2026-07-21; reviewed 2026-08-27"):
    return (
        '# Bug Log\n\nIntroductory conventions.\n\n## OWNER\n\n### Scope\n\n'
        f'<a id="bug-{identity}"></a>\n\n'
        f'- MINOR - {status} ({date}). Shared mechanism. Consequence.\n'
        '  Cause: authority drift. Fixed locally; residual retained.\n'
    )


def test_qualified_metadata_and_complete_paragraph_survive():
    record, = parse_records(_log())
    assert record["status"] == "CLOSED, BOUNDED"
    assert record["date_label"] == "2026-07-21; reviewed 2026-08-27"
    assert record["date"] == "2026-07-21"
    assert record["category"] == "Shared mechanism"
    assert record["text"] == _log().split('</a>\n\n')[1].rstrip('\n')
    lines = _log().splitlines()
    assert '\n'.join(lines[record["line_start"] - 1:record["line_end"]]) == record["text"]


@pytest.mark.parametrize("text", [
    _log().replace('<a id="bug-0001"></a>\n\n', ''),
    _log() + _log(),
    _log().replace('MINOR -', 'UNKNOWN -'),
    _log().replace('2026-07-21;', 'not-a-date;'),
    _log().replace('2026-07-21;', '2026-02-30;'),
    _log().replace('Shared mechanism. Consequence.\n  Cause: authority drift. Fixed locally; residual retained.', 'No category delimiter'),
    _log() + '\n<a id="bug-0002"></a>\n',
    _log() + '\nUnattached consequence.\n',
    _log().replace('bug-0001', 'bug-x'),
    _log().replace('bug-0001', 'bug-00001'),
    _log().replace('bug-0001', 'bug-0000'),
    _log() + '  - MINOR - FIXED (2026-01-01). Hidden record. Consequence.\n',
    _log().replace('## OWNER\n', ''),
    '# Bug Log\n',
])
def test_malformed_or_unaccounted_records_fail(text):
    with pytest.raises(ValueError):
        parse_records(text)


def test_ids_survive_move_and_identical_metadata_is_not_deduplicated():
    first = '## OWNER' + _log().split('## OWNER', 1)[1]
    second = '## OTHER' + _log('0002').split('## OWNER', 1)[1]
    before = {r['id']: r['text'] for r in parse_records(first + second)}
    after = {r['id']: r['text'] for r in parse_records(second + first)}
    assert before == after
    assert len(before) == 2


def test_real_log_is_completely_covered_and_links_resolve():
    records, digest = load_records(DEFAULT_SOURCE)
    text = DEFAULT_SOURCE.read_text(encoding='utf-8')
    assert len(records) == len(re.findall(r'(?m)^- (?:SEVERE|MODERATE|MINOR) - ', text))
    assert len(records) == len({r['id'] for r in records})
    assert len(digest) == 64
    for record in records:
        assert text.count(f'<a id="{record["anchor"]}"></a>') == 1
        assert record['source_link'].endswith('#' + record['anchor'])
    assert any(r['status'] == 'CLOSED, BOUNDED' for r in records)
    assert any('; superseded' in r['date_label'] for r in records)


def test_cross_owner_filters_and_whole_record_batches(tmp_path, capsys):
    source = tmp_path / 'bugs.md'
    source.write_text(_log() + '## OTHER' + _log('0002').split('## OWNER', 1)[1], encoding='utf-8')
    base = ['--source', str(source), '--format', 'jsonl']
    assert main(base + ['--text', 'AUTHORITY', '--text', 'drift', '--category', 'shared',
                       '--status', 'closed, bounded', '--offset', '1', '--limit', '1']) == 0
    captured = capsys.readouterr()
    record = json.loads(captured.out)
    assert record['id'] == 'BUG-0002'
    assert 'residual retained' in record['text']
    assert 'records=2 matched=2 emitted=1 offset=1' in captured.err
    main(base + ['--owner', 'own', '--owner', 'other', '--severity', 'minor'])
    assert len(capsys.readouterr().out.splitlines()) == 2
    main(base + ['--id', 'bug-0001', '--scope', 'scope', '--text', 'absent'])
    captured = capsys.readouterr()
    assert captured.out == ''
    assert 'matched=0 emitted=0' in captured.err


def test_validation_precedes_output_creation_and_filtering(tmp_path):
    source, output = tmp_path / 'bugs.md', tmp_path / 'export.jsonl'
    source.write_text(_log() + '\n- MINOR - FIXED (2026-01-01). Missing ID. Consequence.', encoding='utf-8')
    with pytest.raises(SystemExit) as error:
        main(['--source', str(source), '--id', 'BUG-0001', '--output', str(output)])
    assert error.value.code == 2
    assert not output.exists()


@pytest.mark.parametrize('wrapped', [True, False])
def test_phrase_search_ignores_source_wrapping_without_changing_export(tmp_path, capsys, wrapped):
    text = _log() if wrapped else _log().replace('\n  ', ' ')
    source = tmp_path / 'bugs.md'
    source.write_text(text, encoding='utf-8')
    main(['--source', str(source), '--format', 'jsonl', '--text', 'Consequence. Cause:',
          '--text', 'AUTHORITY\n\tdrift'])
    record = json.loads(capsys.readouterr().out)
    assert record['id'] == 'BUG-0001'
    assert record['text'] == parse_records(text)[0]['text']


def test_export_never_overwrites_existing_destination(tmp_path):
    output = tmp_path / 'existing'
    output.write_text('keep', encoding='utf-8')
    with pytest.raises(SystemExit) as error:
        main(['--output', str(output), '--limit', '1'])
    assert error.value.code == 2
    assert output.read_text(encoding='utf-8') == 'keep'


def test_markdown_preserves_full_entry_and_links_paths_with_spaces(tmp_path, capsys):
    source = tmp_path / 'bug log.md'
    source.write_text(_log(), encoding='utf-8')
    main(['--source', str(source)])
    captured = capsys.readouterr()
    assert f'[BUG-0001](<{source.resolve().as_posix()}#bug-0001>)' in captured.out
    assert parse_records(_log())[0]['text'] in captured.out


def test_cli_from_other_directory_exports_unicode_and_reports_invalid_bounds(tmp_path):
    source = tmp_path / 'bugs.md'
    source.write_text(_log().replace('Consequence', '日本語 consequence'), encoding='utf-8')
    output = tmp_path / 'export.jsonl'
    tool = DEFAULT_SOURCE.parents[1] / 'tools' / 'bugs.py'
    result = subprocess.run(
        [sys.executable, str(tool), '--source', str(source), '--format', 'jsonl', '--output', str(output)],
        cwd=tmp_path, capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert '日本語' in json.loads(output.read_text(encoding='utf-8'))['text']
    result = subprocess.run([sys.executable, str(tool), '--limit', '-1'],
                            cwd=tmp_path, capture_output=True, text=True, timeout=20)
    assert result.returncode == 2
    assert 'must be nonnegative' in result.stderr
    result = subprocess.run([sys.executable, str(tool), '--limit', '1', '--format', 'jsonl'],
                            cwd=tmp_path, capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['source'] == str(DEFAULT_SOURCE.resolve())
