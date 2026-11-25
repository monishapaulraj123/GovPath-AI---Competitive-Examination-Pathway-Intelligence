from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.llm_client import get_llm_status
from app.agents.orchestrator import AgentOrchestrator
from app.database import get_db
from app.engines.planner import build_adaptive_study_plan
from app.engines.rag import RAGEngine
from app.models import ChatMessage, ChatSession, RAGDocument, StudentProfile, User
from app.schemas import ApplyAgentProposalRequest, CounsellorChatRequest, RAGDocumentIngestRequest
from app.security import get_current_user

router = APIRouter(prefix="/api", tags=["AI Counsellor & RAG"])


@router.get("/counsellor/sessions")
def list_chat_sessions(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.updated_at.desc())
        .all()
    )
    return {
        "llm_status": get_llm_status(),
        "sessions": [
            {
                "id": s.id,
                "title": s.title,
                "message_count": len(s.messages),
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            }
            for s in sessions
        ],
    }


@router.post("/counsellor/sessions")
def create_chat_session(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sess = ChatSession(user_id=current_user.id, title="New Counselling Session")
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return {"id": sess.id, "title": sess.title, "messages": []}


@router.get("/counsellor/sessions/{session_id}")
def get_chat_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sess = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
        .first()
    )
    if not sess:
        raise HTTPException(status_code=404, detail="Conversation not found")

    msgs = sorted(sess.messages, key=lambda m: m.id)
    return {
        "id": sess.id,
        "title": sess.title,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "citations": m.citations or [],
                "agent_trace": m.agent_trace or [],
                "proposed_action": m.proposed_action,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in msgs
        ],
    }


@router.delete("/counsellor/sessions/{session_id}")
def delete_chat_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sess = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
        .first()
    )
    if not sess:
        raise HTTPException(status_code=404, detail="Conversation not found")
    db.delete(sess)
    db.commit()
    return {"ok": True}


@router.post("/counsellor/chat")
def counsellor_chat(
    payload: CounsellorChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.session_id:
        sess = (
            db.query(ChatSession)
            .filter(ChatSession.id == payload.session_id, ChatSession.user_id == current_user.id)
            .first()
        )
        if not sess:
            raise HTTPException(status_code=404, detail="Conversation session not found")
    else:
        short_title = payload.message.strip()[:52] + ("..." if len(payload.message.strip()) > 52 else "")
        sess = ChatSession(user_id=current_user.id, title=short_title or "Counselling Session")
        db.add(sess)
        db.flush()

    prior_msgs = sorted(sess.messages, key=lambda m: m.id)[-6:] if payload.session_id else []
    history = [{"role": m.role, "content": m.content[:600]} for m in prior_msgs]

    user_msg = ChatMessage(session_id=sess.id, role="user", content=payload.message.strip())
    db.add(user_msg)
    db.flush()

    orchestrator = AgentOrchestrator()
    result = orchestrator.handle_query(
        db,
        current_user.id,
        payload.message.strip(),
        conversation_history=history,
    )

    assistant_msg = ChatMessage(
        session_id=sess.id,
        role="assistant",
        content=result["reply"],
        citations=result["citations"],
        agent_trace=result["agent_trace"],
        proposed_action=result["proposed_action"],
    )
    db.add(assistant_msg)
    if sess.title == "New Counselling Session":
        sess.title = payload.message.strip()[:52] + ("..." if len(payload.message.strip()) > 52 else "")
    sess.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(assistant_msg)

    return {
        "session_id": sess.id,
        "session_title": sess.title,
        "llm_mode": result["llm_mode"],
        "orchestration_summary": result.get("orchestration_summary"),
        "message": {
            "id": assistant_msg.id,
            "role": "assistant",
            "content": assistant_msg.content,
            "citations": assistant_msg.citations,
            "agent_trace": assistant_msg.agent_trace,
            "proposed_action": assistant_msg.proposed_action,
            "created_at": assistant_msg.created_at.isoformat() if assistant_msg.created_at else None,
        },
    }


@router.post("/counsellor/apply-proposal")
def apply_agent_proposal(
    payload: ApplyAgentProposalRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models import Exam

    valid_exam_ids = {row[0] for row in db.query(Exam.id).all()}
    if payload.proposal_type == "apply_study_plan":
        exam_id = payload.payload.get("exam_id")
        daily_hours = payload.payload.get("daily_hours")
        if exam_id and exam_id not in valid_exam_ids:
            raise HTTPException(status_code=400, detail=f"Unsupported exam_id: {exam_id}")
        if daily_hours is not None:
            try:
                daily_hours = float(daily_hours)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail="Invalid daily_hours value")
            if not (0.5 <= daily_hours <= 16.0):
                raise HTTPException(status_code=400, detail="daily_hours must be between 0.5 and 16.0")
        plan = build_adaptive_study_plan(
            db,
            current_user.id,
            exam_id=exam_id,
            daily_hours=daily_hours,
            persist=True,
        )
        return {"applied": True, "message": "Adaptive study plan updated and activated.", "plan": plan}
    if payload.proposal_type == "update_target_exam":
        exam_id = payload.payload.get("exam_id")
        if not exam_id or exam_id not in valid_exam_ids:
            raise HTTPException(status_code=400, detail=f"Unsupported exam_id: {exam_id}")
        profile = db.query(StudentProfile).filter(StudentProfile.user_id == current_user.id).first()
        if profile:
            profile.primary_target_exam = exam_id
            db.commit()
            return {"applied": True, "message": f"Primary target exam updated to {exam_id}."}
    raise HTTPException(status_code=400, detail="Unsupported proposal type")


@router.get("/rag/documents")
def list_rag_documents(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    docs = db.query(RAGDocument).order_by(RAGDocument.created_at.desc()).all()
    return {
        "documents": [
            {
                "id": d.id,
                "title": d.title,
                "exam_id": d.exam_id,
                "doc_type": d.doc_type,
                "source_name": d.source_name,
                "source_url": d.source_url,
                "verified_status": d.verified_status,
                "chunk_count": d.chunk_count,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in docs
        ]
    }


@router.post("/rag/ingest")
def ingest_rag_document(
    payload: RAGDocumentIngestRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rag = RAGEngine(db)
    doc = rag.ingest_document(
        title=payload.title,
        content=payload.content,
        source_name=payload.source_name,
        exam_id=payload.exam_id or None,
        doc_type=payload.doc_type,
        source_url=payload.source_url,
        verified_status=payload.verified_status,
    )
    return {
        "id": doc.id,
        "title": doc.title,
        "chunk_count": doc.chunk_count,
        "message": "Document chunked, indexed, and added to RAG knowledge base.",
    }


@router.get("/rag/query")
def query_rag(
    q: str,
    exam_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rag = RAGEngine(db)
    return {"query": q, "results": rag.retrieve(q, exam_id=exam_id, top_k=4)}


@router.get("/system/status")
def system_status(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.config import get_settings
    settings = get_settings()
    return {
        "app_name": settings.APP_NAME,
        "database_backend": "PostgreSQL" if "postgresql" in settings.DATABASE_URL else "SQLite (PostgreSQL-ready via DATABASE_URL)",
        "graph_backend": "Neo4j" if settings.NEO4J_URI else "Structured Competency Graph Engine (Neo4j-compatible)",
        "rag_backend": "TF-IDF Cosine Vector Store (SQLite-backed)",
        "llm_status": get_llm_status(),
        "rag_document_count": db.query(RAGDocument).count(),
    }
