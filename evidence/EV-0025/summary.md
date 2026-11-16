# open-bugs: retained claim support

## Adequacy supplement — 2026-11-17

`current.json` is the baseline reproduction: its unsupported `--replace-report`
advice is deliberately not labeled corrected behavior. Fix commit `c0f8da098a7b46f574df70ce6d9ccecab92dc11d`
makes the output-guard flag advice optional. Performance advises a new JSON path;
replacement-capable callers retain their flag. The historical JUnit aggregates
below retain the corrected CLI witnesses and broader external-temp gate. They
prove their named tests, not a newly executed console capture. Source/test blobs
are recoverable from that commit; no current checkout rerun is implied.

```json
{
 "fix_commit": "c0f8da098a7b46f574df70ce6d9ccecab92dc11d",
 "gates": {
  "focused.xml": {
   "input": "build/open-bugs-20261001/focused.xml",
   "sha256": "83f6e8ee9138502e6ff57e6c8aba0f432fe840b464e985fcb711ba5d29d2a578",
   "counts": {
    "tests": 274,
    "failures": 0,
    "errors": 0,
    "skipped": 2
   },
   "guidance_cases": []
  },
  "ordinary-external.xml": {
   "input": "build/open-bugs-20261001/ordinary-external.xml",
   "sha256": "5a29c87d63f90bb45de0b63dd4a9fdd911918675b3243e4f4d2802a49953beca",
   "counts": {
    "tests": 5737,
    "failures": 0,
    "errors": 0,
    "skipped": 4
   },
   "guidance_cases": [
    {
     "name": "test_performance_existing_report_advises_a_new_json_path",
     "passed": true
    }
   ]
  }
 }
}
```
