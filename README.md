# course — SAP ABAP Curriculum Intelligence

Local-first Python toolkit that turns Turkish SAP ABAP training videos into a structured, traceable curriculum (topics, gaps, enrichment, exports).

## Requirements

- Python 3.12+
- Optional: FFmpeg/`ffprobe` for real media metadata
- Optional extras: `whisper`, `visual`, `export`, `llm`

## Install

```bash
uv venv --python 3.12 .venv
uv pip install -e ".[dev]"
```

## Quick start (offline / fake ASR)

```bash
# One-shot synthetic demo
course demo

# Or step by step
course ingest --course demo --path tests/fixtures/synthetic_video/sample.mp4
course transcribe --course demo --adapter fake
course extract-visuals --course demo --extractor stub
course discover-topics --course demo
course map-curriculum
course analyze-gaps --reference tests/fixtures/curriculum_ref/reference.json
course enrich
course content list
course review --list
course export --format all
course status
```

## HTTP API

```bash
uv pip install -e ".[dev]"   # includes fastapi/uvicorn
course serve --host 127.0.0.1 --port 8000
```

Endpoints: `/health`, `/v1/status`, `/v1/courses`, `/v1/courses/{slug}/videos`, `/v1/topics`, `/v1/gaps`, `/v1/jobs`.

## CLI

| Command | Phase |
| --- | --- |
| `course ingest` | 1 |
| `course transcribe` | 1 |
| `course extract-visuals` | 2 |
| `course discover-topics` | 3 |
| `course map-curriculum` | 3 |
| `course analyze-gaps` | 4 |
| `course enrich` | 4 |
| `course review` | 4 |
| `course export` | 5 |
| `course status` | ops |
| `course quality` | coverage / quality signals |
| `course serve` | API |
| `course relations` | edit topic graph |
| `course topics` | inspect topics |
| `course content` | human overrides |
| `course demo` | synthetic full run |
| `course run` | 1–5 orchestration |

Relation examples:

```bash
course relations list
course relations add --from abap-data --to abap-select --type prerequisite
course relations approve <relation-uuid>
course relations delete <relation-uuid>
```


Global flags: `--config`, `--db`, `--data-dir`, `--verbose`, `--quiet`, `--json-logs`.

## Configuration

Defaults live in [`config/default.toml`](config/default.toml). Override with `COURSE_*` env vars or CLI flags.

## Development

```bash
ruff check src tests
mypy src
pytest
```

## Architecture

See [`docs/architecture.md`](docs/architecture.md) and ADRs under [`docs/adr/`](docs/adr/).

## Design rules

- Raw evidence, inferred structure, and generated content stay separated
- Source artifacts are never overwritten
- Pipeline stages are resumable via `(stage, fingerprint)` jobs
- AI-generated material requires human approval before publish
