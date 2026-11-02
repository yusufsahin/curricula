# ADR-002: Separate raw evidence, inferred structure, and generated content

## Status

Accepted

## Context

Summarization-only pipelines blur source video material with AI-written explanations, which is unsafe for training content.

## Decision

Maintain three immutable conceptual layers:

| Layer | Examples | Mutability |
| --- | --- | --- |
| Raw evidence | hashes, Whisper segments, OCR frames | append-only |
| Inferred structure | topics, relationships, gaps | editable and versioned |
| Generated content | explanations, quizzes, ABAP samples | draft → review → approved → published |

## Consequences

Exports and UI must label provenance. Generated examples never appear as source-video content.
