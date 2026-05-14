import json
import os
import urllib.request
from typing import List, Dict, Any, Optional
from app.core.config import settings

def call_ollama_text(
    prompt: str,
    temperature: float = 0.2,
    max_tokens: int = 2000,
    **kwargs,
) -> Optional[str]:
    """Call Ollama API for text generation."""
    try:
        url = f"{settings.OLLAMA_BASE_URL}/api/generate"
        
        body = {
            "model": settings.OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            }
        }
        
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        
        with urllib.request.urlopen(req, timeout=settings.OLLAMA_TIMEOUT) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            return payload.get("response", "").strip()
            
    except Exception as e:
        return f"Ollama Error: {str(e)}"

def call_ollama_chat(
    messages: List[Dict[str, Any]],
    temperature: float = 0.2,
    max_tokens: int = 2000,
    **kwargs,
) -> Dict[str, Any]:
    """Call Ollama API for chat completion."""
    try:
        url = f"{settings.OLLAMA_BASE_URL}/api/chat"
        
        # Convert messages to Ollama format
        ollama_messages = []
        for msg in messages:
            if msg.get("role") == "function":
                # Handle function responses
                for part in msg.get("parts", []):
                    if "functionResponse" in part:
                        ollama_messages.append({
                            "role": "tool",
                            "content": json.dumps(part["functionResponse"]["response"])
                        })
            else:
                content = ""
                if "parts" in msg:
                    for part in msg["parts"]:
                        if "text" in part:
                            content += part["text"]
                        elif "functionCall" in part:
                            content += f"Function call: {json.dumps(part['functionCall'])}"
                else:
                    content = msg.get("content", "")
                
                ollama_messages.append({
                    "role": msg.get("role", "user"),
                    "content": content
                })
        
        body = {
            "model": settings.OLLAMA_MODEL,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            }
        }
        
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        
        with urllib.request.urlopen(req, timeout=settings.OLLAMA_TIMEOUT) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            message = payload.get("message", {})
            
            # Convert Ollama response to Gemini-like format for compatibility
            return {
                "parts": [{"text": message.get("content", "")}]
            }
            
    except Exception as e:
        return {"error": f"Ollama Error: {str(e)}"}

def call_gemini_text(
    prompt: str,
    temperature: float = 0.2,
    max_tokens: int = 2000,
    response_mime_type: Optional[str] = None,
    **kwargs,
) -> Optional[str]:
    # Use Ollama if configured, otherwise fallback to Gemini
    if settings.USE_OLLAMA:
        return call_ollama_text(prompt, temperature, max_tokens, **kwargs)
    
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        return "GEMINI_API_KEY not configured."

    # Stable v1 for pure text generation
    url = f"https://generativelanguage.googleapis.com/v1/models/{settings.GEMINI_MODEL}:generateContent?key={api_key}"
    
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        }
    }
    # Accept and ignore optional parameters like response_mime_type for compatibility
    if response_mime_type:
        body["generationConfig"]["response_mime_type"] = response_mime_type
    
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            candidates = payload.get("candidates", [])
            if candidates:
                return candidates[0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        return f"LLM Error: {str(e)}"
    return None

def call_gemini_with_tools(
    messages: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]] = None,
    temperature: float = 0.0,
    **kwargs,
) -> Dict[str, Any]:
    # Use Ollama for basic chat if configured and no tools are needed
    if settings.USE_OLLAMA and not tools:
        return call_ollama_chat(messages, temperature, **kwargs)
    
    # Fall back to Gemini for tool calling or when Ollama is disabled
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        return {"error": "GEMINI_API_KEY not configured."}

    # IMPORTANT: Tool calling requires 'v1beta' for most Gemini models in standard API
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent?key={api_key}"
    
    body = {
        "contents": messages,
        "generationConfig": {
            "temperature": temperature,
        }
    }
    # Include tools if provided and accept extra kwargs for compatibility
    if tools:
        body["tools"] = tools
    
    # FIX: Ensure response_mime_type is inside generationConfig
    response_mime_type = kwargs.get("response_mime_type")
    if response_mime_type:
        body["generationConfig"]["response_mime_type"] = response_mime_type

    if kwargs:
        # pass-through for backward compatibility; most keys will be ignored by the API
        body.update({k: v for k, v in kwargs.items() if k not in body})
    
    # DEBUG: Print the payload to identify schema mismatches
    # print(f"GEMINI CALL BODY: {json.dumps(body, indent=2)}")

    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            candidates = payload.get("candidates", [])
            if candidates:
                return candidates[0]["content"]
    except urllib.error.HTTPError as he:
        err_msg = he.read().decode("utf-8")
        return {"error": f"HTTP Error {he.code}: {err_msg}"}
    except Exception as e:
        return {"error": str(e)}
    return {}

def extract_json_object_text(text: str) -> Dict[str, Any]:
    try:
        # Find the first { and last }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            return json.loads(text[start:end+1])
    except:
        pass
    return {}


def clean_response(text: str) -> str:
    if not text:
        return ""
    remove_patterns = [
        "Consider the following conversation history",
        "History:",
        "USER:",
        "ASSISTANT:",
        "Current Question:",
        "based on retrieved documents:",
        "Topic:",
        "Content:"
    ]
    out = text
    for pattern in remove_patterns:
        if pattern in out:
            out = out.split(pattern)[-1]
    return out.strip()


def format_final_output(answer: str, citations: List[Dict[str, Any]], confidence: float, source: str, confidence_reason: str = "") -> Dict[str, Any]:
    clean = clean_response(answer)
    out = {
        "answer": clean,
        "citations": citations or [],
        "confidence": float(confidence) if confidence is not None else 0.0,
        "source": source or ""
    }
    if confidence_reason:
        out["confidence_reason"] = confidence_reason
    return out
