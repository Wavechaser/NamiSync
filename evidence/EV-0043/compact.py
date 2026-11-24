"""Validate and compact the diagnostic matrix; this is not a release gate."""
import collections
import hashlib
import importlib.metadata
import json
import platform
import sys
from pathlib import Path

here = Path(__file__).resolve().parent
root = here.parents[1]
rows = json.loads((here / 'out/matrix.json').read_text(encoding='utf-8-sig'))
assert len(rows) == 8
assert [r['dwmHandled'] for r in rows] == [0, 0, 0, 0, 240, 0, 0, 240]
foreground = json.loads((here / 'out/m09-foreground.json').read_text())
restored = json.loads((here / 'out/m10-restored.json').read_text())
points = foreground['button_points']
assert len(points) == 15
assert all(p['actual'] == p['expected'] and p['receiver_is_form'] for p in points)
assert foreground['geometry']['webview_rect'] == foreground['geometry']['extended']
assert foreground['geometry']['client_origin'] == [0, -12]
assert foreground['geometry']['webview_origin'] == [0, 0]
assert not restored['geometry']['maximized']
assert restored['geometry']['client_origin'] == restored['geometry']['webview_origin']
clean = here.parent / 'm2-a2-max-clean'
restore_runs = {name: json.loads((clean / 'out' / filename).read_text()) for name, filename in
                (('baseline', 'restore-baseline.json'), ('candidate', 'restore-check.json'),
                 ('candidate_native_commands', 'restore-native.json'))}
assert all(r['restored_sizes'] == [[1925,1260], [1925,1312], [1925,1364]] for r in restore_runs.values())
summary = {
    'authority': 'Diagnostic observations on this profile, not product acceptance',
    'repository_head': 'bd005c07b9f83f0184037fdfe07b10fd030a3b99',
    'python': sys.version, 'windows': platform.platform(),
    'packages': {name: importlib.metadata.version(name) for name in ('pywebview','pythonnet')},
    'sources_sha256': {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in (root / 'evidence/EV-0042/framing-proto.py', here / 'probe.py', here / 'matrix.ps1',
                                 here / 'fresh-check.py', clean / 'probe.py', clean / 'probe-baseline.py', clean / 'probe-native.py')},
    'webview2_sdk_file_version': '1.0.3856.49',
    'grid': '600 UI-thread DwmDefWindowProc calls: x=window.right-300..right step 10; y=max(0,window.top)..+100 step 5',
    'matrix': [{k: r[k] for k in ('name','config','geometry','dwmHandled','hitCodes')} for r in rows],
    'foreground_candidate': {
        'geometry': foreground['geometry'],
        'dwm_hit_counts': dict(collections.Counter(p[2] for p in foreground['dwm_handled_grid'])),
        'button_rectangles_screen': [foreground['titlebar_rects'][i] for i in (2,3,5)],
        'boundary_recipe': 'Four inside corners and center of each TITLEBARINFOEX rectangle; WM_NCHITTEST and WindowFromPoint',
        'correct_button_results': 15, 'form_is_real_input_receiver': 15, 'points': 15},
    'restored_candidate': {'geometry': restored['geometry']},
    'separate_restore_size_finding': {name: {k:v for k,v in r.items() if k != 'observations'}
                                    for name,r in restore_runs.items()},
    'limitations': [
        'Matrix ran occluded: its WindowFromPoint results were invalid for routing and are not counted; m09 foreground check is the routing witness.',
        'Stock native caption also declines DwmDefWindowProc: this diagnostic count is not evidence that stock caption hover fails.',
        'User confirmed hover, Snap Layouts and alignment on the padded candidate with metric-adjusted carve; exact TITLEBARINFOEX carve was subsequently checked at all 15 boundary points.',
        'No fresh mixed-DPI, high-contrast or snapped-window acceptance claimed.',
        'Fresh candidate-only and baseline-only runs both grow restored height by 52 physical pixels per cycle. Same result through native system commands. Cause and fix remain uninvestigated; this is not introduced by the caption-hover candidate.'
    ],
    'validation': 'All compaction assertions passed',
}
(here / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
print('PASS: 8 variants; maximized candidate 15/15 hit codes and 15/15 form receivers; page fits visible frame; restored padding is zero.')
