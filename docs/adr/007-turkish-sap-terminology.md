# ADR-007: Turkish explanations with canonical SAP/ABAP terms

## Status

Accepted

## Context

Training audiences are Turkish-speaking; SAP/ABAP technical terms must remain searchable and standard.

## Decision

Default locale is `tr`. Topic labels and explanations are Turkish. ABAP keywords and SAP object names stay in their canonical English/ABAP form.

## Consequences

Normalizers and exporters must not translate technical tokens. Glossaries keep bilingual entries where useful.
