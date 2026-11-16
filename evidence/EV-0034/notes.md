Notes for "Root admission optimization (2026-09-28)": text files chosen from `build/root-admission-optimization-20260928/`, verbatim, each under an H1 naming its source path. Non-Markdown files are fenced. JSON is in `data.json`.

# `build/root-admission-optimization-20260928/baseline/dependencies.txt`

````text
bottle==0.13.4
cffi==2.1.0
click==8.4.2
clr_loader==0.3.1
colorama==0.4.6
grimp==3.15
import-linter==2.13
iniconfig==2.3.0
markdown-it-py==4.2.0
mdurl==0.1.2
packaging==26.2
pluggy==1.6.0
proxy_tools==0.1.0
pycparser==3.0
Pygments==2.20.0
pytest==9.1.1
pythonnet==3.1.0
pywebview==6.2.1
rich==15.0.0
setuptools==83.0.0
typing_extensions==4.16.0
xxhash==3.8.1
````

# `build/root-admission-optimization-20260928/baseline/runtime.txt`

````text
F:\GitHubRepositories\NamiSync\.venv\Scripts\python.exe
3.13.14 (tags/v3.13.14:fd17997, Jun 10 2026, 13:03:48) [MSC v.1944 64 bit (AMD64)]
Windows-11-10.0.26200-SP0
````

# `build/root-admission-optimization-20260928/executor/exfat-handle-metadata.log`

````text
[
  {
    "path": "K:\\NamiSyncExecutorHoldWitness-20260928-diagnostic\\test_execute_held_root_blocks_0\\source\\file.bin",
    "access": "FILE_READ_ATTRIBUTES",
    "queries": [
      {
        "name": "FileBasicInfo",
        "class": 0,
        "succeeded": true,
        "winerror": 0
      },
      {
        "name": "FileStandardInfo",
        "class": 1,
        "succeeded": true,
        "winerror": 0
      },
      {
        "name": "FileIdInfo",
        "class": 18,
        "succeeded": false,
        "winerror": 87
      }
    ],
    "native_stat_handle": {
      "winerror": 87,
      "message": "[WinError 87] The parameter is incorrect.",
      "frames": [
        "observe",
        "_stat_handle",
        "file_identity_from_windows_handle"
      ]
    },
    "closed": true
  },
  {
    "path": "F:\\GitHubRepositories\\NamiSync\\namisync\\core\\root_authority.py",
    "access": "FILE_READ_ATTRIBUTES",
    "queries": [
      {
        "name": "FileBasicInfo",
        "class": 0,
        "succeeded": true,
        "winerror": 0
      },
      {
        "name": "FileStandardInfo",
        "class": 1,
        "succeeded": true,
        "winerror": 0
      },
      {
        "name": "FileIdInfo",
        "class": 18,
        "succeeded": true,
        "winerror": 0
      }
    ],
    "native_stat_handle": {
      "succeeded": true
    },
    "closed": true
  }
]
````
