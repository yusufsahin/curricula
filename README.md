# Curricula

Local-first toolkit that turns Turkish SAP ABAP training videos into a structured, traceable curriculum (topics, gaps, enrichment, exports).

**Repo:** https://github.com/yusufsahin/curricula

## Requirements

- Python 3.12+
- Optional: FFmpeg/`ffprobe` for real media metadata
- Optional extras: `whisper`, `visual`, `export`, `llm`, `api`

## Install

```bash
uv venv --python 3.12 .venv
uv pip install -e ".[dev]"
```

## Quick start (offline / fake ASR)

```bash
# One-shot synthetic demo
curricula demo

# Or step by step
curricula ingest --course demo --path tests/fixtures/synthetic_video/sample.mp4
curricula transcribe --course demo --adapter fake
curricula extract-visuals --course demo --extractor stub
curricula discover-topics --course demo
curricula map-curriculum
curricula analyze-gaps --reference tests/fixtures/curriculum_ref/reference.json
curricula enrich
curricula content list
curricula review --list
curricula export --format all
curricula status
curricula quality
```

## HTTP API

```bash
curricula serve --host 127.0.0.1 --port 8000
```

Endpoints: `/health`, `/v1/status`, `/v1/courses`, `/v1/courses/{slug}/videos`, `/v1/topics`, `/v1/gaps`, `/v1/jobs`.

## CLI

Primary command: `curricula` (alias: `course`).

| Command | Phase |
| --- | --- |
| `curricula ingest` | 1 |
| `curricula transcribe` | 1 |
| `curricula extract-visuals` | 2 |
| `curricula discover-topics` | 3 |
| `curricula map-curriculum` | 3 |
| `curricula analyze-gaps` | 4 |
| `curricula enrich` | 4 |
| `curricula review` | 4 |
| `curricula export` | 5 |
| `curricula status` | ops |
| `curricula quality` | coverage / quality signals |
| `curricula serve` | API |
| `curricula relations` | edit topic graph |
| `curricula topics` | inspect topics |
| `curricula content` | human overrides |
| `curricula demo` | synthetic full run |
| `curricula run` | 1–5 orchestration |

```bash
curricula relations list
curricula relations add --from abap-data --to abap-select --type prerequisite
curricula topics list
curricula content override <id> --text "..."
```

Global flags: `--config`, `--db`, `--data-dir`, `--verbose`, `--quiet`, `--json-logs`.

## Configuration

Defaults live in [`config/default.toml`](config/default.toml). Override with `CURRICULA_*` env vars or CLI flags.

## Development

```bash
ruff check src tests
mypy src
pytest
```

See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Architecture

See [`docs/architecture.md`](docs/architecture.md) and ADRs under [`docs/adr/`](docs/adr/).

## Design rules

- Raw evidence, inferred structure, and generated content stay separated
- Source artifacts are never overwritten
- Pipeline stages are resumable via `(stage, fingerprint)` jobs
- AI-generated material requires human approval before publish
