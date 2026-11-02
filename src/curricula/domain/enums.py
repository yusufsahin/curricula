"""Shared domain enumerations."""

from __future__ import annotations

from enum import StrEnum


class ProcessingStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ReviewStatus(StrEnum):
    UNREVIEWED = "unreviewed"
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"


class EnrichmentStatus(StrEnum):
    NONE = "none"
    QUEUED = "queued"
    GENERATING = "generating"
    DRAFT = "draft"
    APPROVED = "approved"
    PUBLISHED = "published"


class GapClass(StrEnum):
    MISSING = "missing"
    INSUFFICIENT = "insufficient"
    UNCERTAIN = "uncertain"
    COMPLETE = "complete"


class RelationshipType(StrEnum):
    PREREQUISITE = "prerequisite"
    RELATED = "related"
    PART_OF = "part_of"
    SEE_ALSO = "see_also"


class ContentKind(StrEnum):
    EXPLANATION = "explanation"
    EXAMPLE = "example"
    EXERCISE = "exercise"
    QUIZ = "quiz"
    GLOSSARY = "glossary"
    OBJECTIVE = "objective"


class EvidenceLayer(StrEnum):
    RAW = "raw"
    INFERRED = "inferred"
    GENERATED = "generated"


class PipelineStage(StrEnum):
    INGEST = "ingest"
    TRANSCRIBE = "transcribe"
    EXTRACT_VISUALS = "extract-visuals"
    DISCOVER_TOPICS = "discover-topics"
    MAP_CURRICULUM = "map-curriculum"
    ANALYZE_GAPS = "analyze-gaps"
    ENRICH = "enrich"
    REVIEW = "review"
    EXPORT = "export"


class VideoStatus(StrEnum):
    PENDING = "pending"
    INGESTED = "ingested"
    TRANSCRIBING = "transcribing"
    TRANSCRIBED = "transcribed"
    FAILED = "failed"


class SourceRefType(StrEnum):
    TRANSCRIPT = "transcript"
    FRAME = "frame"
    CODE = "code"
    MANUAL = "manual"
