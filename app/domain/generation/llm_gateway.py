import json
import os
import re
import time
from typing import List, Dict, Any, Optional
from app.core.config import settings
from app.core.logging import logger

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

_GENAI_CLIENT: Optional[Any] = None

def get_genai_client() -> Optional[Any]:
    global _GENAI_CLIENT
    if _GENAI_CLIENT is not None:
        return _GENAI_CLIENT

    api_key = getattr(settings, "GEMINI_API_KEY", None) or os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY is not configured.")
        return None

    if genai is not None:
        try:
            _GENAI_CLIENT = genai.Client(api_key=api_key)
            return _GENAI_CLIENT
        except Exception as e:
            logger.error(f"Failed to create google.genai.Client: {e}")
            return None
    return None


def call_gemini_text(
    prompt: str,
    temperature: float = 0.2,
    max_tokens: int = 2048,
    response_mime_type: Optional[str] = "application/json",
    retries: int = 2,
    **kwargs,
) -> Optional[str]:
    """Generate text/JSON using the verified active models on your Gemini API key."""
    client = get_genai_client()
    if client is None:
        return "LLM Error: GEMINI_API_KEY or google-genai SDK not available."

    # Use the verified active models from your API account
    models_to_try = [
        "gemini-2.5-flash",
        "gemini-flash-latest",
        "gemini-2.5-flash-lite",
        "gemini-flash-lite-latest",
        "gemini-pro-latest"
    ]

    config = types.GenerateContentConfig(
        temperature=temperature,
        max_output_tokens=max_tokens,
        response_mime_type=response_mime_type if response_mime_type else "text/plain"
    ) if types else None

    for model_name in models_to_try:
        for attempt in range(retries + 1):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=config
                )
                if response and response.text:
                    return response.text.strip()
            except Exception as e:
                err_msg = str(e)
                if "429" in err_msg and attempt < retries:
                    logger.warning(f"Rate limit on {model_name}. Retrying in 2.5s ({attempt+1}/{retries})...")
                    time.sleep(2.5)
                    continue
                logger.warning(f"Attempt with model {model_name} failed: {err_msg[:120]}")
                break

    return "LLM Error: Could not generate response with candidate Gemini models."


def call_gemini_with_tools(
    messages: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]] = None,
    temperature: float = 0.0,
    **kwargs,
) -> Dict[str, Any]:
    client = get_genai_client()
    if client is None:
        return {"error": "GEMINI_API_KEY or SDK not configured."}

    try:
        last_msg = ""
        if messages and "parts" in messages[-1]:
            parts = messages[-1]["parts"]
            if parts and isinstance(parts[0], dict) and "text" in parts[0]:
                last_msg = parts[0]["text"]
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=last_msg or "Hello",
            config=types.GenerateContentConfig(temperature=temperature) if types else None
        )
        return {
            "parts": [{"text": response.text if response else ""}]
        }
    except Exception as e:
        return {"error": str(e)}


def extract_json_object_text(text: str) -> Dict[str, Any]:
    """Robust parser for JSON wrapped in markdown or raw text."""
    if not text:
        return {}
    clean = text.strip()
    if "```" in clean:
        clean = re.sub(r"^```(?:json)?\s*", "", clean, flags=re.MULTILINE)
        clean = re.sub(r"```\s*$", "", clean, flags=re.MULTILINE).strip()
    try:
        return json.loads(clean)
    except Exception:
        pass
    try:
        start = clean.find("{")
        end = clean.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(clean[start:end+1])
    except Exception:
        pass
    return {}


def clean_response(text: str) -> str:
    """Cleans raw assistant responses and strips out technical/prompt headers."""
    if not text:
        return ""
    remove_patterns = [
        r"^Consider the following conversation history.*?\n\n",
        r"^History:.*?\n\n",
        r"^Current Question:.*?\n\n",
        r"^Topic:.*?\n\n",
        r"^USER:.*?\n\n",
        r"^ASSISTANT:.*?\n\n"
    ]
    out = text
    for pattern in remove_patterns:
        out = re.sub(pattern, "", out, flags=re.DOTALL | re.IGNORECASE)
    return out.strip()


def format_final_output(
    answer: str, 
    citations: List[Dict[str, Any]], 
    confidence: Any, 
    source: str, 
    key_points: Optional[List[str]] = None,
    confidence_reason: str = ""
) -> Dict[str, Any]:
    try:
        conf_float = float(confidence)
        if conf_float > 1.0:
            conf_float = conf_float / 100.0
    except (ValueError, TypeError):
        conf_float = 0.95 if citations else 0.50

    return {
        "answer": clean_response(answer),
        "citations": citations or [],
        "key_points": key_points or [],
        "confidence": round(conf_float, 2),
        "source": source or "Uploaded Document",
        "confidence_reason": confidence_reason
    }