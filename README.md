# NamiSync
A safety-first, one-way file mirroring app for Windows. NamiSync performs source to target syncs, database-based maintenance, and integrity tracking features. 

## Development setup

NamiSync requires Python 3.13 or later. Create and activate a virtual
environment, then install the development dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Run the test suite with:

```powershell
.\.venv\Scripts\python.exe -m pytest
```
