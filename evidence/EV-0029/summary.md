# R2 third-party notice inputs — summary

Commit `1f632b13` (2026-11-09, "finalize M1 distribution notices and native
origins") committed the R2 notice set to `tools/packaging/notices/`.
`manifest.json` there is the authority for every notice text: name, version,
upstream source URL, archive hash where one applies, and the SHA-256 of the
committed text. Commit `eb98c95f` (2026-11-10) later re-pinned records 27–31
from CPython 3.13.17 to the 3.15.2 release runtime. The 3.13.17 state below is
the R2 state; `git show 1f632b13:tools/packaging/notices/manifest.json`
reproduces it.

## What R2 added

Records 01–25 were written from pinned sources: the installed CPython
LICENSE.txt, plus CPython, cpython-source-deps and PyPI wheel members. Their
upstream URL and text hash are in the manifest. R2's source review then found
notices that the aggregate package licenses omit, and added six records:

| Record | Finding | Upstream input |
| --- | --- | --- |
| 26 PyInstaller bootloader zlib | The Windows bootloader statically links an inflate-only subset of zlib 1.3.2. This is separate from CPython's zlib 1.3.1. | PyInstaller v6.22.3 `bootloader/zlib/LICENSE`, with its README |
| 27 HACL* hash implementations | The license header is byte-identical in the MD5, SHA1, SHA2 and SHA3 sources that `PCbuild/pythoncore.vcxproj` compiles. | CPython v3.13.17 `Modules/_hacl/Hacl_Hash_*.c` |
| 28 HACL* KaRaMeL headers | Five compiler-reachable krml headers carry the same INRIA/Microsoft Apache-2.0 header. The full Apache-2.0 text is in the OpenSSL and PyInstaller entries. | CPython v3.13.17 `Modules/_hacl/include/krml/` |
| 29–31 CPython decimal wrapper, Windows API support, getopt | Each has its own leading copyright/license comment. The record keeps that comment as the excerpt. | CPython v3.13.17 `_decimal.c`, `_winapi.c`, `getopt.c` |

The construction scripts asserted the manifest's record count before each
append, so each record has a fixed number. They also asserted that the copied
headers were identical (HACL*) or carried the expected terms (krml).

## Coverage

The source review followed the selected Python Windows projects: 19 projects,
290 direct references and 790 resolved source/include paths. It also followed
45 PyInstaller bootloader C/header files. The bootloader files are grouped by
notice set in the `m1-r2-distribution` candidate. These are finite coverage
observations for this build, not a claim about future dependency builds
(TOOLS, R2 validation).

## Pinned upstream inputs

The CPython install is `python-3.13.17-amd64.zip`, SHA-256
`b26ca4b4ee51e157836049934d2b8eabd55939be296f3130254251b6df96ec2f`. Its
install receipt is in `data.json`. The downloaded sources the review read:

| Upstream file | Bytes | SHA-256 |
| --- | --- | --- |
| https://raw.githubusercontent.com/python/cpython/v3.13.17/Modules/_hacl/Hacl_Hash_MD5.c | 38,499 | `f71cf6a0e8f09354c2af2c785a1d36e0cba7613a589be01ca8a3d8478f4c8874` |
| https://raw.githubusercontent.com/python/cpython/v3.13.17/Modules/_hacl/Hacl_Hash_SHA1.c | 13,043 | `5b29bd9951646861e0e19427be5d923a5bab7a4516824ccc068f696469195eec` |
| https://raw.githubusercontent.com/python/cpython/v3.13.17/Modules/_hacl/Hacl_Hash_SHA2.c | 36,131 | `30638efb75c8b185bb09c3df6977e3f3c5d21a1e696218cf7ade6bc4d5201b31` |
| https://raw.githubusercontent.com/python/cpython/v3.13.17/Modules/_hacl/Hacl_Hash_SHA3.c | 21,450 | `17c0db96d40d1849f02546d5f55428fa89b61b07748d5b5df45cec25c5f29c0f` |
| https://raw.githubusercontent.com/python/cpython/v3.13.17/Modules/_hacl/include/krml/FStar_UInt_8_16_32_64.h | 3,026 | `65decdb74c24049aa19430462a51219250cfc65d8c162778e42df88b3142fa42` |
| https://raw.githubusercontent.com/python/cpython/v3.13.17/Modules/_hacl/include/krml/internal/target.h | 10,653 | `d16a59f37a1d4982626870e370889eb9d332a9ad035661b8062f549fc734d061` |
| https://raw.githubusercontent.com/python/cpython/v3.13.17/Modules/_hacl/include/krml/lowstar_endianness.h | 7,757 | `3734c7942bec9a434e16df069fa45bdcb84b130f14417bc5f7bfe8546272d9f5` |
| https://raw.githubusercontent.com/python/cpython/v3.13.17/Modules/_hacl/include/krml/FStar_UInt128_Verified.h | 9,342 | `455e94f24a0900deda7e6e36f4714e4253d32cea077f97e23f90c569a717bc48` |
| https://raw.githubusercontent.com/python/cpython/v3.13.17/Modules/_hacl/include/krml/fstar_uint128_struct_endianness.h | 1,649 | `fe57e1bc5ce3224d106e36cb8829b5399c63a68a70b0ccd0c91d82a4565c8869` |
| https://raw.githubusercontent.com/python/cpython/v3.13.17/Modules/_decimal/_decimal.c | 184,254 | `6ce1c04d434bf15cfeb8f83edf5b6eb2f2d020c8c0b998f4d10de3a55c43cbf6` |
| https://raw.githubusercontent.com/python/cpython/v3.13.17/Modules/_winapi.c | 96,345 | `4600aafe91a8bf0574665d71ba515331c6decc7c1985e7861b9a458b19a650c0` |
| https://raw.githubusercontent.com/python/cpython/v3.13.17/Python/getopt.c | 4,817 | `65f0db353ec829f73eb09af141fcd551f2e2cc169d6f6313f69af12cc42c8670` |
| https://raw.githubusercontent.com/pyinstaller/pyinstaller/v6.22.3/bootloader/zlib/README | 278 | `44293b0513e0e7c42e0ceef9e0c87eff752820d964fb418ae06c63b421c013bf` |
