"""Make a fresh-process candidate-only probe, without stock-frame transitions."""
from pathlib import Path
import sys

here = Path(__file__).resolve().parent
target = here.parent / 'm2-a2-max-clean'
source = (here / 'probe.py').read_text(encoding='utf-8')
start = source.index('def worker():')
end = source.index('\n\nthreading.Thread(target=worker', start)
driver = '''def worker():
    while not instance or not instance.wv_hwnd:
        time.sleep(.2)
    time.sleep(2)
    candidate = dict(inset=0, zero_return=True, pad=True, correct_carve=True, native_hit=True)
    observations = []
    for i, maximized in enumerate((False, True, False, True, False)):
        ui(lambda: apply(dict(candidate, name=f"fresh-{i}", maximized=maximized)))
        time.sleep(.6)
        observations.append(ui(geometry))
    restored = [g for g in observations if not g['maximized']]
    sizes = [[g['window'][2]-g['window'][0], g['window'][3]-g['window'][1]] for g in restored]
    result = dict(observations=observations, restored_sizes=sizes,
                  stable_restore_size=all(s == sizes[0] for s in sizes),
                  max_page_fits=all(g['webview_rect'] == g['extended'] for g in observations if g['maximized']),
                  restored_padding_zero=all(g['client_origin'] == g['webview_origin'] for g in restored))
    (p.OUT / 'restore-check.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    import webview
    webview.windows[0].destroy()
'''
mode = sys.argv[1] if len(sys.argv) > 1 else 'candidate'
if mode == 'baseline':
    driver = driver.replace('candidate = dict(inset=0, zero_return=True, pad=True, correct_carve=True, native_hit=True)', 'candidate = {}')
if mode == 'native':
    driver = driver.replace('ui(lambda: apply(dict(candidate, name=f"fresh-{i}", maximized=maximized)))',
                            'ui(lambda: apply(dict(candidate, name=f"fresh-{i}")))\n        ui(lambda: p.user32.SendMessageW(instance.hwnd, 0x0112, 0xF030 if maximized else 0xF120, 0))')
if mode != 'candidate':
    driver = driver.replace("'restore-check.json'", repr('restore-' + mode + '.json'))
name = 'probe.py' if mode == 'candidate' else 'probe-' + mode + '.py'
(target / name).write_text(source[:start] + driver + source[end:], encoding='utf-8')
