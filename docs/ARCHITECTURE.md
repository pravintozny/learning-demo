# Architecture

- `lms/models.py`: dataclasses and the in-memory `Store` (dicts keyed by integer id, one
  counter per entity type).
- One service class per domain area, each taking the shared `Store`. Services that need
  others receive them via the constructor (`GradingService` -> `AssessmentService`,
  `ProgressService` -> courses/enrollments/grading, `AnalyticsService` -> all).
- `lms/system.py` builds the graph; an injectable `clock` makes dates deterministic in tests.
- Errors derive from `LMSError`: `NotFoundError`, `ValidationError`, `EnrollmentError`
  (with `PrerequisiteError`), `AttemptLimitError`.
- Persistence is out of scope; swapping `Store` for a database layer is the extension point.
