import json
import os
import urllib.request
from typing import List, Dict, Any, Optional
from app.core.config import settings

def call_gemini_text(
    prompt: str,
    temperature: float = 0.2,
    max_tokens: int = 2000,
    response_mime_type: Optional[str] = None,
    **kwargs,
) -> Optional[str]:
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        return "GEMINI_API_KEY not configured."

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent?key={api_key}"
    
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
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        return {"error": "GEMINI_API_KEY not configured."}

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
