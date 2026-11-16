Notes for "AB-7 final evidence for the Plan Again investigation (2026-09-25)": text files chosen from `build/post-m1-8-ablation-20260925/`, verbatim, each under an H1 naming its source path. Non-Markdown files are fenced. JSON is in `data.json`.

# `build/post-m1-8-ablation-20260925/ab7-final-evidence/test_m1_4_installed_task_shell0/data/logs/namisync.log`

````text
2026-09-25T17:24:09.708Z INFO pid=45664 thread=MainThread logger=namisync: startup.begin product_version=0.1.0 python_version=3.13.14 os_version=Windows-11-10.0.26200-SP0
2026-09-25T17:24:09.739Z INFO pid=45664 thread=MainThread logger=namisync: startup.dependencies pywebview=6.2.1 pythonnet=3.1.0 clr_loader=0.3.1 bottle=0.13.4
2026-09-25T17:24:10.807Z INFO pid=45664 thread=Dummy-23 logger=namisync: startup.renderer browser_version=153.0.4234.48
2026-09-25T17:24:11.109Z INFO pid=45664 thread=namisync-command-create_task logger=namisync: bridge.refused request_id=3dfe5d36be6d6a133d1f5113a15d06f3 command=create_task code=task_unavailable
2026-09-25T17:24:11.182Z INFO pid=45664 thread=namisync-command-close_task logger=namisync: bridge.refused request_id=678729e880ea1a1bed84225dd785f437 command=close_task code=bridge_unavailable
2026-09-25T17:24:11.490Z INFO pid=45664 thread=Thread-232 (_call) logger=namisync: bridge.refused request_id=b55e78eef3d8868581de77d580af252c command=open_plan_view code=task_unavailable
2026-09-25T17:24:11.533Z INFO pid=45664 thread=Thread-254 (_call) logger=namisync: bridge.refused request_id=6bfb436430e385c75d4a51362e28ac68 command=next_events code=task_unavailable
2026-09-25T17:24:12.120Z INFO pid=45664 thread=Thread-365 (_call) logger=namisync: bridge.refused request_id=ac4e0140cdbed0e5fa24e7294caa87aa command=open_plan_view code=task_unavailable
2026-09-25T17:24:15.316Z INFO pid=45664 thread=Thread-445 (_call) logger=namisync: bridge.refused request_id=046035fd57f17f7eafb6f05c459eb518 command=open_plan_view code=task_unavailable
2026-09-25T17:24:27.279Z WARNING pid=45664 thread=Dummy-23 logger=pywebview: Failed to delete user data folder: [WinError 32] The process cannot access the file because it is being used by another process: 'C:\\Users\\Spectrum\\AppData\\Local\\Temp\\NamiSync-ab7-final-20260926-02\\test_m1_4_installed_task_shell0\\data\\webview2'
2026-09-25T17:24:27.283Z INFO pid=45664 thread=MainThread logger=namisync: shutdown.complete
````
