"""Artifact version helpers."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from course.db.models import ArtifactVersion
from course.domain.ids import new_id


def next_artifact_version(
    session: Session,
    *,
    entity_type: str,
    entity_id: str,
    payload_path: str,
    created_by: str = "system",
    parent_version_id: UUID | None = None,
) -> ArtifactVersion:
    current = session.scalar(
        select(func.max(ArtifactVersion.version)).where(
            ArtifactVersion.entity_type == entity_type,
            ArtifactVersion.entity_id == entity_id,
        )
    )
    version = int(current or 0) + 1
    row = ArtifactVersion(
        id=new_id(),
        entity_type=entity_type,
        entity_id=entity_id,
        version=version,
        payload_path=payload_path,
        created_by=created_by,
        parent_version_id=parent_version_id,
    )
    session.add(row)
    session.flush()
    return row
