"""
Structured Government Examination Competency Knowledge Graph Engine.
Represents Exam -> Subject -> Topic -> Competency nodes, prerequisite edges,
required mastery depths, and cross-exam transfer pathways.
"""

from collections import defaultdict
from typing import Any, Optional
from sqlalchemy.orm import Session
from app.models import Competency, Exam, ExamCompetencyRequirement, Subject


class CompetencyGraphEngine:
    """In-memory structured graph built dynamically from database entities with optional Neo4j export."""

    def __init__(self, db: Session):
        self.db = db
        self.exams = {e.id: e for e in db.query(Exam).all()}
        self.subjects = {s.id: s for s in db.query(Subject).all()}
        self.competencies = {c.id: c for c in db.query(Competency).all()}
        self.requirements = db.query(ExamCompetencyRequirement).all()

        self.exam_reqs: dict[str, dict[str, ExamCompetencyRequirement]] = defaultdict(dict)
        self.comp_exams: dict[str, list[ExamCompetencyRequirement]] = defaultdict(list)
        for req in self.requirements:
            self.exam_reqs[req.exam_id][req.competency_id] = req
            self.comp_exams[req.competency_id].append(req)

    def get_full_graph(
        self,
        exam_id: Optional[str] = None,
        subject_id: Optional[str] = None,
        student_scores: Optional[dict[str, float]] = None,
    ) -> dict[str, Any]:
        """Return nodes and edges suitable for graph traversal and interactive UI visualization."""
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        added_nodes: set[str] = set()
        student_scores = student_scores or {}

        target_exams = [self.exams[exam_id]] if exam_id and exam_id in self.exams else list(self.exams.values())
        relevant_comp_ids: set[str] = set()

        for ex in target_exams:
            ex_node_id = f"EXAM:{ex.id}"
            if ex_node_id not in added_nodes:
                nodes.append({
                    "id": ex_node_id,
                    "raw_id": ex.id,
                    "label": ex.short_name,
                    "full_label": ex.name,
                    "node_type": "Exam",
                    "category": ex.category,
                    "difficulty_index": ex.difficulty_index,
                })
                added_nodes.add(ex_node_id)

            for comp_id, req in self.exam_reqs.get(ex.id, {}).items():
                comp = self.competencies.get(comp_id)
                if not comp:
                    continue
                if subject_id and comp.subject_id != subject_id:
                    continue
                relevant_comp_ids.add(comp_id)

                subj = self.subjects.get(comp.subject_id)
                subj_node_id = f"SUBJECT:{comp.subject_id}"
                if subj and subj_node_id not in added_nodes:
                    nodes.append({
                        "id": subj_node_id,
                        "raw_id": subj.id,
                        "label": subj.name,
                        "node_type": "Subject",
                        "domain": subj.domain,
                    })
                    added_nodes.add(subj_node_id)

                topic_node_id = f"TOPIC:{comp.subject_id}:{comp.topic_name}"
                if topic_node_id not in added_nodes:
                    nodes.append({
                        "id": topic_node_id,
                        "raw_id": comp.topic_name,
                        "label": comp.topic_name,
                        "node_type": "Topic",
                        "subject_id": comp.subject_id,
                    })
                    added_nodes.add(topic_node_id)
                    edges.append({
                        "id": f"e:{subj_node_id}->{topic_node_id}",
                        "source": subj_node_id,
                        "target": topic_node_id,
                        "edge_type": "HAS_TOPIC",
                    })

                comp_node_id = f"COMP:{comp.id}"
                if comp_node_id not in added_nodes:
                    linked_exams = [r.exam_id for r in self.comp_exams.get(comp.id, [])]
                    nodes.append({
                        "id": comp_node_id,
                        "raw_id": comp.id,
                        "label": comp.name,
                        "node_type": "Competency",
                        "subject_id": comp.subject_id,
                        "topic_name": comp.topic_name,
                        "subtopics": comp.subtopics,
                        "linked_exams": linked_exams,
                        "transfer_breadth": len(linked_exams),
                        "student_score": round(student_scores.get(comp.id, 0.0), 1),
                    })
                    added_nodes.add(comp_node_id)
                    edges.append({
                        "id": f"e:{topic_node_id}->{comp_node_id}",
                        "source": topic_node_id,
                        "target": comp_node_id,
                        "edge_type": "DEVELOPS_COMPETENCY",
                    })

                edges.append({
                    "id": f"e:{ex_node_id}->{subj_node_id}",
                    "source": ex_node_id,
                    "target": subj_node_id,
                    "edge_type": "TESTS_SUBJECT",
                })
                edges.append({
                    "id": f"e:{ex_node_id}->{comp_node_id}",
                    "source": ex_node_id,
                    "target": comp_node_id,
                    "edge_type": "REQUIRES_COMPETENCY",
                    "required_depth": req.required_depth,
                    "weightage_percent": req.weightage_percent,
                    "exam_subject_label": req.exam_subject_label,
                })

        # Deduplicate subject-exam edges
        seen_edge_ids: set[str] = set()
        unique_edges: list[dict[str, Any]] = []
        for edge in edges:
            if edge["id"] not in seen_edge_ids:
                seen_edge_ids.add(edge["id"])
                unique_edges.append(edge)

        # Add prerequisite edges among relevant competencies
        for comp_id in relevant_comp_ids:
            comp = self.competencies[comp_id]
            for prereq_id in comp.prerequisites or []:
                if prereq_id in relevant_comp_ids:
                    unique_edges.append({
                        "id": f"e:PREREQ:{prereq_id}->{comp_id}",
                        "source": f"COMP:{prereq_id}",
                        "target": f"COMP:{comp_id}",
                        "edge_type": "PREREQUISITE_OF",
                    })

        return {
            "nodes": nodes,
            "edges": unique_edges,
            "stats": {
                "exam_count": sum(1 for n in nodes if n["node_type"] == "Exam"),
                "subject_count": sum(1 for n in nodes if n["node_type"] == "Subject"),
                "topic_count": sum(1 for n in nodes if n["node_type"] == "Topic"),
                "competency_count": sum(1 for n in nodes if n["node_type"] == "Competency"),
                "edge_count": len(unique_edges),
                "backend_mode": "Structured Graph Engine (Neo4j-compatible schema)",
            },
        }

    def query_shared_competencies(self, source_exam_id: str, target_exam_id: str) -> dict[str, Any]:
        """Traverse graph to compute structural overlap and depth differences between two exams."""
        src_reqs = self.exam_reqs.get(source_exam_id, {})
        tgt_reqs = self.exam_reqs.get(target_exam_id, {})

        shared = []
        target_only = []
        source_only = []

        for cid, treq in tgt_reqs.items():
            comp = self.competencies.get(cid)
            if not comp:
                continue
            if cid in src_reqs:
                sreq = src_reqs[cid]
                shared.append({
                    "competency_id": cid,
                    "competency_name": comp.name,
                    "subject_id": comp.subject_id,
                    "topic_name": comp.topic_name,
                    "source_depth": sreq.required_depth,
                    "target_depth": treq.required_depth,
                    "depth_delta": round(treq.required_depth - sreq.required_depth, 1),
                    "target_weightage": treq.weightage_percent,
                })
            else:
                target_only.append({
                    "competency_id": cid,
                    "competency_name": comp.name,
                    "subject_id": comp.subject_id,
                    "topic_name": comp.topic_name,
                    "target_depth": treq.required_depth,
                    "target_weightage": treq.weightage_percent,
                })

        for cid, sreq in src_reqs.items():
            if cid not in tgt_reqs:
                comp = self.competencies.get(cid)
                if comp:
                    source_only.append({
                        "competency_id": cid,
                        "competency_name": comp.name,
                        "subject_id": comp.subject_id,
                        "source_depth": sreq.required_depth,
                    })

        return {
            "source_exam_id": source_exam_id,
            "target_exam_id": target_exam_id,
            "shared": shared,
            "target_only": target_only,
            "source_only": source_only,
            "structural_overlap_percent": round(
                (len(shared) / max(1, len(tgt_reqs))) * 100.0, 1
            ),
        }

    def get_competency_neighbors(self, competency_id: str) -> dict[str, Any]:
        comp = self.competencies.get(competency_id)
        if not comp:
            return {"error": f"Competency {competency_id} not found"}
        reqs = self.comp_exams.get(competency_id, [])
        dependents = [
            c.id for c in self.competencies.values() if competency_id in (c.prerequisites or [])
        ]
        return {
            "competency_id": comp.id,
            "name": comp.name,
            "subject_id": comp.subject_id,
            "topic_name": comp.topic_name,
            "subtopics": comp.subtopics,
            "prerequisites": comp.prerequisites,
            "unlocks_competencies": dependents,
            "required_by_exams": [
                {
                    "exam_id": r.exam_id,
                    "exam_name": self.exams[r.exam_id].short_name if r.exam_id in self.exams else r.exam_id,
                    "required_depth": r.required_depth,
                    "weightage_percent": r.weightage_percent,
                    "subject_label": r.exam_subject_label,
                }
                for r in reqs
            ],
        }
