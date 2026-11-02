"""Export curriculum artifacts."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import networkx as nx
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from course.config import Settings
from course.curriculum.mapper import MapCurriculumService
from course.db.models import (
    Assessment,
    CodeSnippet,
    ContentBlock,
    KnowledgeGap,
    Topic,
    TopicRelationship,
)
from course.domain.enums import RelationshipType

logger = logging.getLogger(__name__)


class ExportRequest:
    def __init__(
        self,
        *,
        formats: list[str],
        out_dir: Path | None = None,
    ) -> None:
        self.formats = formats
        self.out_dir = out_dir


class ExportService:
    def __init__(
        self,
        settings: Settings,
        session_factory: sessionmaker[Session],
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory

    def run(self, req: ExportRequest) -> list[Path]:
        out_dir = req.out_dir or self.settings.paths.exports_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        written: list[Path] = []
        formats = req.formats
        if "all" in formats:
            formats = [
                "json",
                "md",
                "mermaid",
                "graphml",
                "abap",
                "assessments",
                "coverage",
                "docx",
            ]

        with self.session_factory() as session:
            curriculum = self._curriculum_payload(session)
            if "json" in formats:
                path = out_dir / "curriculum.json"
                path.write_text(
                    json.dumps(curriculum, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                written.append(path)
            if "md" in formats:
                written.extend(self._write_topic_markdown(session, out_dir / "topics"))
            if "mermaid" in formats:
                path = out_dir / "topic_map.mmd"
                path.write_text(self._mermaid(session), encoding="utf-8")
                written.append(path)
            if "graphml" in formats:
                path = out_dir / "topic_map.graphml"
                mapper = MapCurriculumService(self.settings, self.session_factory)
                graph = mapper.build_graph(session)
                nx.write_graphml(graph, path)
                written.append(path)
            if "abap" in formats:
                written.extend(self._write_abap_repo(session, out_dir / "abap"))
            if "assessments" in formats:
                path = out_dir / "assessment_bank.json"
                path.write_text(
                    json.dumps(self._assessments(session), ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                written.append(path)
            if "coverage" in formats:
                path = out_dir / "coverage_report.md"
                path.write_text(self._coverage_report(session), encoding="utf-8")
                written.append(path)
            if "docx" in formats:
                path = out_dir / "handbook.docx"
                self._write_docx(curriculum, path)
                written.append(path)
            if "pdf" in formats:
                # Lightweight PDF stand-in: write markdown handbook for Phase 5 without heavy deps
                path = out_dir / "handbook.pdf.md"
                path.write_text(self._handbook_markdown(curriculum), encoding="utf-8")
                written.append(path)

        # MkDocs stub site
        mkdocs_dir = out_dir / "mkdocs"
        mkdocs_dir.mkdir(parents=True, exist_ok=True)
        (mkdocs_dir / "mkdocs.yml").write_text(
            "site_name: SAP ABAP Curriculum\nnav:\n  - Home: index.md\n",
            encoding="utf-8",
        )
        (mkdocs_dir / "docs").mkdir(exist_ok=True)
        (mkdocs_dir / "docs" / "index.md").write_text(
            "# SAP ABAP Curriculum\n\nExported by `course export`.\n",
            encoding="utf-8",
        )
        written.append(mkdocs_dir / "mkdocs.yml")
        return written

    def _curriculum_payload(self, session: Session) -> dict[str, object]:
        topics = list(session.scalars(select(Topic)).all())
        rels = list(session.scalars(select(TopicRelationship)).all())
        id_to_stable = {t.id: t.stable_id for t in topics}
        return {
            "topics": [
                {
                    "stable_id": t.stable_id,
                    "title_tr": t.title_tr,
                    "title_canonical": t.title_canonical,
                    "summary": t.summary,
                    "confidence": t.confidence,
                    "review_status": t.review_status,
                    "enrichment_status": t.enrichment_status,
                    "source_order": t.source_order,
                    "learning_order": t.learning_order,
                }
                for t in sorted(
                    topics,
                    key=lambda x: (x.learning_order is None, x.learning_order or 0),
                )
            ],
            "relationships": [
                {
                    "from": id_to_stable.get(r.from_topic_id),
                    "to": id_to_stable.get(r.to_topic_id),
                    "type": r.type,
                    "approved": r.approved,
                    "source": r.source,
                }
                for r in rels
            ],
        }

    def _write_topic_markdown(self, session: Session, out_dir: Path) -> list[Path]:
        out_dir.mkdir(parents=True, exist_ok=True)
        written: list[Path] = []
        for topic in session.scalars(select(Topic)).all():
            blocks = list(
                session.scalars(
                    select(ContentBlock).where(ContentBlock.topic_id == topic.id)
                ).all()
            )
            lines = [
                f"# {topic.title_tr}",
                "",
                f"Canonical: `{topic.title_canonical}`",
                f"Stable ID: `{topic.stable_id}`",
                "",
            ]
            if topic.summary:
                lines.extend([topic.summary, ""])
            for block in blocks:
                label = "AI-GENERATED DRAFT" if block.layer == "generated" else block.layer
                lines.extend(
                    [
                        f"## {block.kind} ({label})",
                        "",
                        block.body_md,
                        "",
                    ]
                )
            path = out_dir / f"{topic.stable_id}.md"
            path.write_text("\n".join(lines), encoding="utf-8")
            written.append(path)
        return written

    def _mermaid(self, session: Session) -> str:
        lines = ["flowchart TD"]
        for topic in session.scalars(select(Topic)).all():
            safe = topic.stable_id.replace("-", "_")
            label = topic.title_tr.replace('"', "'")
            lines.append(f'  {safe}["{label}"]')
        for rel in session.scalars(
            select(TopicRelationship).where(
                TopicRelationship.type == RelationshipType.PREREQUISITE.value
            )
        ).all():
            topics = {t.id: t.stable_id for t in session.scalars(select(Topic)).all()}
            src = topics.get(rel.from_topic_id, "unknown").replace("-", "_")
            dst = topics.get(rel.to_topic_id, "unknown").replace("-", "_")
            lines.append(f"  {src} --> {dst}")
        return "\n".join(lines) + "\n"

    def _write_abap_repo(self, session: Session, out_dir: Path) -> list[Path]:
        out_dir.mkdir(parents=True, exist_ok=True)
        written: list[Path] = []
        for idx, snippet in enumerate(session.scalars(select(CodeSnippet)).all()):
            origin = "generated" if snippet.is_generated else "source"
            path = out_dir / f"{origin}_{idx:03d}.abap"
            header = (
                "* AI-GENERATED — not from source video\n"
                if snippet.is_generated
                else "* Extracted from source video OCR\n"
            )
            path.write_text(header + snippet.code_text + "\n", encoding="utf-8")
            written.append(path)
        return written

    def _assessments(self, session: Session) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        topics = {t.id: t.stable_id for t in session.scalars(select(Topic)).all()}
        for item in session.scalars(select(Assessment)).all():
            rows.append(
                {
                    "topic": topics.get(item.topic_id),
                    "kind": item.kind,
                    "review_status": item.review_status,
                    "is_generated": item.is_generated,
                    "payload": json.loads(item.payload_json),
                }
            )
        return rows

    def _coverage_report(self, session: Session) -> str:
        topics = list(session.scalars(select(Topic)).all())
        gaps = list(session.scalars(select(KnowledgeGap)).all())
        blocks = list(session.scalars(select(ContentBlock)).all())
        lines = [
            "# Content coverage report",
            "",
            f"- Topics: {len(topics)}",
            f"- Knowledge gaps: {len(gaps)}",
            f"- Content blocks: {len(blocks)}",
            "",
            "## Gaps by class",
            "",
        ]
        by_class: dict[str, int] = {}
        for gap in gaps:
            by_class[gap.gap_class] = by_class.get(gap.gap_class, 0) + 1
        for cls, count in sorted(by_class.items()):
            lines.append(f"- {cls}: {count}")
        lines.extend(["", "## Topics", ""])
        gaps_by_topic: dict[object, list[KnowledgeGap]] = {}
        for gap in gaps:
            gaps_by_topic.setdefault(gap.topic_id, []).append(gap)
        blocks_by_topic: dict[object, list[ContentBlock]] = {}
        for block in blocks:
            blocks_by_topic.setdefault(block.topic_id, []).append(block)
        for topic in sorted(topics, key=lambda t: t.stable_id):
            topic_gaps = gaps_by_topic.get(topic.id, [])
            topic_blocks = blocks_by_topic.get(topic.id, [])
            worst = "complete"
            for gap in topic_gaps:
                if gap.gap_class == "missing":
                    worst = "missing"
                    break
                if gap.gap_class == "insufficient" and worst != "missing":
                    worst = "insufficient"
                if gap.gap_class == "uncertain" and worst == "complete":
                    worst = "uncertain"
            lines.append(
                f"- `{topic.stable_id}` — {topic.title_tr}: "
                f"coverage={worst}, gaps={len(topic_gaps)}, blocks={len(topic_blocks)}"
            )
        lines.append("")
        return "\n".join(lines)

    def _topics_list(self, curriculum: dict[str, object]) -> list[dict[str, object]]:
        raw = curriculum.get("topics", [])
        if not isinstance(raw, list):
            return []
        return [t for t in raw if isinstance(t, dict)]

    def _handbook_markdown(self, curriculum: dict[str, object]) -> str:
        lines = ["# SAP ABAP Course Handbook", ""]
        for topic in self._topics_list(curriculum):
            lines.append(f"## {topic.get('title_tr')}")
            lines.append(f"Canonical: {topic.get('title_canonical')}")
            lines.append("")
        return "\n".join(lines)

    def _write_docx(self, curriculum: dict[str, object], path: Path) -> None:
        try:
            from docx import Document
        except ImportError:
            # Fallback: write markdown sibling so export still succeeds offline
            path.with_suffix(".md").write_text(
                self._handbook_markdown(curriculum), encoding="utf-8"
            )
            path.write_text(
                "DOCX dependency missing; see handbook.md\n", encoding="utf-8"
            )
            return
        doc = Document()
        doc.add_heading("SAP ABAP Course Handbook", 0)
        for topic in self._topics_list(curriculum):
            doc.add_heading(str(topic.get("title_tr")), level=1)
            doc.add_paragraph(f"Canonical: {topic.get('title_canonical')}")
            if topic.get("summary"):
                doc.add_paragraph(str(topic.get("summary")))
        doc.save(path)
