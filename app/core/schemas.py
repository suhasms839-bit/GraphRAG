from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import List, Optional

# User Schemas
class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str
    full_name: str
    role: str
    department: Optional[str] = None
    organization: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    full_name: str
    role: str
    department: Optional[str]
    organization: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

# Document Schemas
class DocumentResponse(BaseModel):
    id: int
    filename: str
    file_size: int
    mime_type: str
    uploaded_at: datetime
    ingested: bool = False
    chunk_count: int = 0
    ingest_log: Optional[str] = None
    graph_ready: bool = False
    
    class Config:
        from_attributes = True

class DocumentListResponse(BaseModel):
    documents: List[DocumentResponse]
    total_count: int

# Message Schemas
class MessageResponse(BaseModel):
    id: int
    role: str
    content: str
    citations: Optional[str]
    key_points: Optional[str]
    confidence: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True

# Conversation Schemas
class ConversationResponse(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime
    messages: List[MessageResponse] = []
    
    class Config:
        from_attributes = True

class ConversationListResponse(BaseModel):
    conversations: List[ConversationResponse]
    total_count: int

# Chat Request/Response
class ChatRequest(BaseModel):
    conversation_id: Optional[int] = None  # For new conversations, leave None
    question: str
    topic: Optional[str] = "General"

class ChatResponse(BaseModel):
    conversation_id: int
    message_id: int
    answer: str
    key_points: List[str]
    citations: List[dict]
    confidence: float
    confidence_label: Optional[str] = "Medium"
    source_type: Optional[str] = "Retrieved documents"

# Database setup request
class InitializeDBRequest(BaseModel):
    setup_demo: bool = False
