from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
import json
import os
from app.core.database import get_db
from app.core.models import User, Conversation, Message, Document
from app.core.schemas import ChatRequest, ChatResponse, ConversationResponse, ConversationListResponse
from app.core.security import verify_token
from app.core.logging import logger
from app.domain.generation.answer_engine import answer_with_rag
from app.domain.learning.course_builder import CourseBuilder
from app.infrastructure.vectorstore.manager import VectorStoreManager
from app.domain.retrieval.hybrid_search import HybridRetriever
from app.domain.agents.orchestrator import AgenticOrchestrator
import traceback

router = APIRouter(prefix="/api/chat", tags=["chat"])

def get_current_user(authorization: str = Header(None), db: Session = Depends(get_db)):
    """Extract and verify JWT token from Authorization header"""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing"
        )
    
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header"
        )
    
    token = parts[1]
    payload = verify_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    
    user_id = int(payload.get("sub"))
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user

@router.post("/message", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Send a message in conversation and get response"""
    
    # Get or create conversation
    if request.conversation_id:
        conversation = db.query(Conversation).filter(
            (Conversation.id == request.conversation_id) & 
            (Conversation.user_id == current_user.id)
        ).first()
        
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )
    else:
        # Create new conversation
        conversation = Conversation(
            user_id=current_user.id,
            title=request.question[:50]  # Use first 50 chars as title
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    
    # Store user message
    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=request.question
    )
    db.add(user_message)
    db.commit()
    db.refresh(user_message)
    
    # Get conversation history for context
    conversation_history = db.query(Message).filter(
        Message.conversation_id == conversation.id
    ).order_by(Message.created_at).all()
    
    # Build concise history context for follow-up questions.
    history_messages = conversation_history[:-1]
    history_context = "\n".join([
        f"{msg.role.upper()}: {msg.content}"
        for msg in history_messages[-8:]
    ])

    # FIX 5: Use AgenticOrchestrator instead of direct answer_with_rag
    try:
        manager = VectorStoreManager(user_id=current_user.id)
        orchestrator = AgenticOrchestrator(manager)

        enriched_question = request.question
        if history_context:
            enriched_question = (
                "Consider the following conversation history when answering the current question.\n\n"
                f"History:\n{history_context}\n\n"
                f"Current Question: {request.question}"
            )

        # Check documents count for initial status
        user_documents = db.query(Document).filter(Document.user_id == current_user.id).all()
        
        # Execute Agentic RAG
        result = await orchestrator.run(
            question=enriched_question,
            topic_title=request.topic or "General"
        )

        # Process the agentic result
        answer = result.get("answer", "I couldn't generate a proper response.")
        key_points = result.get("key_points", [])
        citations = result.get("citations", [])
        confidence_rate = result.get("confidence", 0.5)
        confidence_label = "High" if confidence_rate >= 0.75 else ("Medium" if confidence_rate >= 0.5 else "Low")
        
        # Determine source footer for v3.0 explainability
        unique_sources = set([c.get("source", "Unknown") for c in citations])
        source_footer = f"Retrieved documents: {', '.join(list(unique_sources))}" if unique_sources else "General Knowledge"
        
        # Append v3.0 metadata headers to the final answer string
        final_answer_text = f"{answer}\n\n[Source]\n- {source_footer}\n\n[Confidence]\n{confidence_label}"

        chat_response = ChatResponse(
            conversation_id=conversation.id,
            message_id=user_message.id + 1,
            answer=final_answer_text,
            key_points=key_points,
            citations=citations,
            confidence=confidence_rate,
            confidence_label=confidence_label,
            source_type=source_footer
        )

        # Store assistant message in DB
        bot_message = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=final_answer_text,
            citations=json.dumps(citations),
            confidence=confidence_label
        )
        db.add(bot_message)
        db.commit()

        return chat_response

    except Exception as e:
        # Log full traceback and return structured error to frontend
        tb = traceback.format_exc()
        logger.error(f"Chat generation failed: {e}\n{tb}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat generation failed: {str(e)}"
        )


@router.get("/debug/retrieval")
async def debug_retrieval(q: str, current_user: User = Depends(get_current_user)):
    """Debug endpoint: return top-k retrieval hits for given query for the current user with scores and mode."""
    try:
        manager = VectorStoreManager(user_id=current_user.id)
        retriever = HybridRetriever(manager)
        resp = await retriever.retrieve(q, topic_title="Debug", k=5)

        # Build debug payload
        detailed = resp.get("detailed_hits", [])
        scores = resp.get("scores", [])
        hits = resp.get("hits", [])
        mode = resp.get("mode", "unknown")

        return {
            "query": q,
            "mode": mode,
            "top_score": resp.get("top_score", 0.0),
            "confidence": resp.get("confidence", 0.0),
            "scores": scores,
            "chunks": [{"content": h.get("content"), "metadata": h.get("metadata")} for h in hits],
            "reranked": detailed
        }
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(f"Debug retrieval failed: {e}\n{tb}")
        raise HTTPException(status_code=500, detail="Debug retrieval failed; check server logs.")

@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all conversations for current user"""
    
    conversations = db.query(Conversation).filter(
        Conversation.user_id == current_user.id
    ).order_by(Conversation.updated_at.desc()).all()
    
    return ConversationListResponse(
        conversations=[ConversationResponse.from_orm(conv) for conv in conversations],
        total_count=len(conversations)
    )

@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific conversation with all messages"""
    
    conversation = db.query(Conversation).filter(
        (Conversation.id == conversation_id) &
        (Conversation.user_id == current_user.id)
    ).first()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    return ConversationResponse.from_orm(conversation)

@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a conversation"""
    
    conversation = db.query(Conversation).filter(
        (Conversation.id == conversation_id) &
        (Conversation.user_id == current_user.id)
    ).first()
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    db.delete(conversation)
    db.commit()
    
    logger.info(f"Conversation deleted: {conversation_id} by user {current_user.id}")
    
    return {"message": "Conversation deleted successfully"}
