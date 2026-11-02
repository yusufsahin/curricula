# Architecture

## Overview

`course` is a local-first modular monolith that turns Turkish SAP ABAP training videos into a traceable curriculum. Pipeline stages are resumable, artifacts are append-only, and AI-generated material requires human approval before publish.

## Layers

1. **Raw evidence** — videos, transcript segments, visual frames, OCR text
2. **Inferred structure** — topics, concepts, relationships, knowledge gaps
3. **Generated content** — explanations, examples, exercises, assessments

## Pipeline

```text
ingest → transcribe → extract-visuals → discover-topics
       → map-curriculum → analyze-gaps → enrich → review → export
```

Each stage records a `ProcessingJob` with an input fingerprint. Matching completed jobs are skipped unless forced.

## Module map

| Package | Responsibility |
| --- | --- |
| `course.media` | Ingest, hashing, ffprobe metadata |
| `course.transcription` | Turkish ASR, normalization, artifacts |
| `course.visual` | Scene detection, OCR, code extraction (Phase 2+) |
| `course.topics` | Topic discovery and taxonomy (Phase 3+) |
| `course.curriculum` | Prerequisite graph and learning order (Phase 3+) |
| `course.gaps` | Coverage vs reference curriculum (Phase 4+) |
| `course.enrichment` | Draft generative content (Phase 4+) |
| `course.review` | Human approval workflow (Phase 4+) |
| `course.export` | JSON/MD/DOCX/PDF/MkDocs (Phase 5+) |
| `course.pipeline` | Contracts, jobs, orchestration |
| `course.db` | SQLAlchemy models and repositories |
| `course.cli` | Typer commands |

## Data flow

Videos are hashed and registered. Transcription writes raw JSON plus normalized Markdown while preserving `text_raw` in the database. Later stages consume prior artifacts and emit new ones under `data/`. The SQLite database stores entities, relationships, job metrics, and provenance paths.
