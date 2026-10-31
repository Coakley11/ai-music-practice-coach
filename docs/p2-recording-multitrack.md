# Recording identity and Multitrack exports

Command Center must count recording resources rather than storage deliveries. Recording Analysis allocates a detached resource UUID when a file is prepared. The same ID survives fallback and SQLite copies, including Command Center's sibling-fallback import path. Music's deployment shim remains cloud-first. The later analyzed-media catalog has its own identity lifecycle. The preparation signature includes full-file content and the uploader token, so reruns reuse a take while an explicit new selection can be distinct even with the same filename/bytes. No audio or hash is sent as activity metadata.

Multitrack layer saves are edits, not recording-upload milestones. First-layer ownership is bound once, persisted in project/page metadata, and cleared on a new project/reset. Legacy projects without authoritative source metadata stay unowned. A rendered WAV captures its source/project ID, audible track count, duration and format at mixing; later UI edits do not relabel its activity. Canonical media normalizers retain the new fields through save/reload.

Only a stored export emits `multitrack_export_saved`, using its canonical export ID and a small allowlist. Activity failure is caught after media persistence. Ordinary reruns do not save another export; explicit Save Export retains the existing product behavior of creating a distinct resource. No layer/mixer events, audio payloads or creative documents are reported.

No Multitrack Resume is exposed: a durable project ID and layers do not by themselves prove exact cold restoration of source/song/instrument/key and destination. P0/P1 entry and preservation paths are unchanged.

Regression coverage: `test_p2_multitrack_activity.py`, media catalog/export/storage, mixer and ownership tests, P0 cold preservation, P1 lifecycle/identity and existing Resume/progress tests. The local `.p2` audit/report holds actual Chromium acceptance evidence and final results.
