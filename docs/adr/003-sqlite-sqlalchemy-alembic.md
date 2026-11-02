# ADR-003: SQLite + SQLAlchemy 2.0 + Alembic

## Status

Accepted

## Context

The system must run locally without external database services while remaining schema-migratable.

## Decision

Use SQLite as the system of record, SQLAlchemy 2.0 for ORM access, and Alembic for migrations. NetworkX builds in-memory graph views from `TopicRelationship`; the database remains authoritative.

## Consequences

Graph algorithms are application-side. Very large corpora may later need Postgres, but curriculum-scale workloads fit SQLite.
