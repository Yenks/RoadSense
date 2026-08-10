# RSZSIS Desktop App

## Pipeline Reuse Approach

The desktop app is a sibling wrapper around the existing working pipeline. At runtime it resolves `../school-zone-safety-system` relative to this app folder and prepends that directory to `sys.path`, then imports `app.*` modules directly.

This keeps detection, tracking, speed estimation, violation detection, database models, and importer code owned by the existing project. The only existing-pipeline edit is an output refactor in `app/safety/pipeline.py`: `ViolationPipeline.run()` now accepts optional frame/progress/stop callbacks, emits annotated frames before any `cv2.imshow()` path, and writes the Week 5 speed log that the existing DB importer already requires.

Discrepancy found during inspection: `app/database/importer.py` requires `data/processed/<video>_week5_speed.json`, but `app/safety/pipeline.py` previously only wrote the Week 6 violations log and did not call `import_video()` despite its docstring saying fresh runs populate the DB automatically. The desktop worker now runs the pipeline, calls `import_video()` on success, and syncs the resulting local rows to Supabase.

Additional discrepancy: the requested History violation detail includes a confidence column, but `app/database/models.py` defines `Violation` without any confidence field and the confirmed Supabase schema also has no confidence column. The desktop table keeps the column visible and renders `N/A` so no false confidence value is fabricated.

Live Processing uses `app.safety.pipeline.ViolationPipeline` (not `app.speed.pipeline.SpeedPipeline`), because that pipeline already runs detection → tracking → speed → violations and supplies the Live stats.

Task 7 login uses `supabase-py`'s `sign_in_with_password({"email", "password"})` credentials dict (not positional args). AuthManager creates a client with `SUPABASE_ANON_KEY` only; SyncManager creates a separate client with `SUPABASE_SERVICE_KEY` for data writes. The "Generate detailed log" checkbox stays checked by default and is intentionally inert when unchecked — logs are required by `import_video()` and kept for debugging.
