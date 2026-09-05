from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

from app.agent import graph
from app.routes.auth import get_current_user
from app.db import create_chat, get_chat, get_user_chats, update_chat_history, delete_chat

router = APIRouter(prefix="/api", tags=["chat"])

# In-memory store for guest user sessions to save DB storage
# guest_memory[session_id] = {"summary": "", "recent_messages": []}
guest_memory: Dict[str, Dict[str, Any]] = {}

class ChatRequest(BaseModel):
    session_id: str
    message: str

@router.post("/chat")
def chat(request: ChatRequest, current_user: Optional[dict] = Depends(get_current_user)):
    session_id = request.session_id
    message = request.message
    
    if current_user:
        # Registered user workflow (Neon DB)
        user_id = current_user["user_id"]
        
        # Fetch existing chat or create a new entry
        chat_data = get_chat(session_id, user_id)
        is_new = False
        if not chat_data:
            title = message[:40].strip() + ("..." if len(message) > 40 else "")
            chat_data = create_chat(user_id, session_id, title)
            is_new = True
            
        summary = chat_data.get("summary", "")
        recent = chat_data.get("recent_messages", []) or []
        
        # Invoke LangGraph agent with summary and recent window
        state = {
            "question": message,
            "answer": "",
            "summary": summary,
            "recent_messages": recent,
            "messages": [],
            "tool_steps": []
        }
        
        try:
            response = graph.invoke(state)
        except Exception as e:
            err_msg = str(e)
            if "RESOURCE_EXHAUSTED" in err_msg or "429" in err_msg or "Quota exceeded" in err_msg:
                return {
                    "answer": "Gemini API Quota Exceeded: You have temporarily exceeded your Google Gemini free tier request limit. Please wait a minute before retrying, or check your API key billing details on Google AI Studio.",
                    "summary": summary,
                    "recent_messages": recent,
                    "tool_steps": []
                }
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Agent invocation failed: {str(e)}"
            )
            
        # Extract response payloads
        updated_summary = response.get("summary", "")
        updated_recent = response.get("recent_messages", [])
        tool_steps = response.get("tool_steps", [])
        
        # Update database details
        title_update = None
        if is_new:
            title_update = message[:40].strip() + ("..." if len(message) > 40 else "")
            
        update_chat_history(session_id, user_id, updated_summary, updated_recent, title=title_update)
        
        return {
            "answer": response["answer"],
            "summary": updated_summary,
            "recent_messages": updated_recent,
            "tool_steps": tool_steps
        }
    else:
        # Guest user workflow (In-Memory)
        if session_id not in guest_memory:
            guest_memory[session_id] = {
                "summary": "",
                "recent_messages": []
            }
            
        session_data = guest_memory[session_id]
        
        state = {
            "question": message,
            "answer": "",
            "summary": session_data["summary"],
            "recent_messages": session_data["recent_messages"],
            "messages": [],
            "tool_steps": []
        }
        
        try:
            response = graph.invoke(state)
        except Exception as e:
            err_msg = str(e)
            if "RESOURCE_EXHAUSTED" in err_msg or "429" in err_msg or "Quota exceeded" in err_msg:
                return {
                    "answer": "⚠️ **Gemini API Quota Exceeded**: You have temporarily exceeded your Google Gemini free tier request limit. Please wait a minute before retrying, or check your API key billing details on Google AI Studio.",
                    "summary": session_data["summary"],
                    "recent_messages": session_data["recent_messages"],
                    "tool_steps": []
                }
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Agent invocation failed: {str(e)}"
            )
            
        guest_memory[session_id]["summary"] = response.get("summary", "")
        guest_memory[session_id]["recent_messages"] = response.get("recent_messages", [])
        
        return {
            "answer": response["answer"],
            "summary": response.get("summary", ""),
            "recent_messages": response.get("recent_messages", []),
            "tool_steps": response.get("tool_steps", [])
        }


@router.get("/chats")
def list_chats(current_user: dict = Depends(get_current_user)):
    """Retrieve all chats for the logged in user."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return get_user_chats(current_user["user_id"])

@router.get("/chats/{chat_id}")
def get_chat_detail(chat_id: str, current_user: dict = Depends(get_current_user)):
    """Retrieve a single chat detail."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    chat_data = get_chat(chat_id, current_user["user_id"])
    if not chat_data:
        raise HTTPException(status_code=404, detail="Chat not found")
    return chat_data

@router.delete("/chats/{chat_id}")
def delete_user_chat(chat_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a chat session."""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    success = delete_chat(chat_id, current_user["user_id"])
    if not success:
        raise HTTPException(status_code=404, detail="Chat not found or deletion failed")
    return {"message": "Chat deleted successfully"}