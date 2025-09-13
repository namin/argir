from __future__ import annotations
import os
from typing import Optional, Union, Any
from contextvars import ContextVar

class LLMConfigurationError(Exception): ...
class LLMNotConfigured(LLMConfigurationError): ...
class LLMCallError(RuntimeError): ...

CACHE_LLM = os.getenv("CACHE_LLM") is not None
if CACHE_LLM:
    try:
        from joblib import Memory  # type: ignore
        _HAVE_JOBLIB = True
    except Exception:
        _HAVE_JOBLIB = False
        Memory = None  # type: ignore
else:
    _HAVE_JOBLIB = False
    Memory = None  # type: ignore

_HAVE_GENAI = False
try:
    from google import genai  # type: ignore
    from google.genai import types  # type: ignore
    _HAVE_GENAI = True
except Exception:
    _HAVE_GENAI = False
    genai = None  # type: ignore
    types = None  # type: ignore

LLM_MODEL = os.getenv("LLM_MODEL", "gemini-2.5-flash")
_GOOGLE_LOCATION_DEFAULT = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

_request_api_key: ContextVar[Optional[str]] = ContextVar('request_api_key', default=None)

_memory = None
if _HAVE_JOBLIB and CACHE_LLM:
    _memory = Memory(os.path.expanduser(os.getenv("LLM_CACHE_DIR", ".cache/llm")), verbose=0)

def set_request_api_key(api_key: Optional[str]) -> None:
    _request_api_key.set(api_key)

def get_request_api_key() -> Optional[str]:
    try: return _request_api_key.get()
    except LookupError: return None

def init_llm_client(api_key: Optional[str] = None,
                    project: Optional[str] = None,
                    location: Optional[str] = None,
                    required: bool = True):
    if not _HAVE_GENAI:
        if required: raise LLMNotConfigured("google-genai not available. `pip install google-genai`.")
        return None
    gemini_api_key = api_key or get_request_api_key() or os.getenv("GEMINI_API_KEY")
    google_cloud_project = project or os.getenv("GOOGLE_CLOUD_PROJECT")
    google_cloud_location = location or _GOOGLE_LOCATION_DEFAULT
    try:
        if gemini_api_key:
            return genai.Client(api_key=gemini_api_key)
        if google_cloud_project:
            return genai.Client(vertexai=True, project=google_cloud_project, location=google_cloud_location)
    except Exception as e:
        if required: raise LLMConfigurationError(f"Failed to init google-genai client: {e}")
        return None
    if required: raise LLMNotConfigured("Set GEMINI_API_KEY or GOOGLE_CLOUD_PROJECT.")
    return None

def generate_content(client, contents: Union[str, list], config=None, model: str = LLM_MODEL):
    if _memory is None:
        return client.models.generate_content(model=model, contents=contents, config=config)
    @(_memory.cache)  # type: ignore
    def _cached_call(contents, m, cfg_repr):
        resp = client.models.generate_content(model=m, contents=contents, config=config)
        return getattr(resp, "text", None) or getattr(resp, "output_text", None) or ""
    text = _cached_call(contents, model, repr(config))
    class Resp: 
        def __init__(self, t): self.text=t
    return Resp(text)

def generate_json(prompt: str, *, system: Optional[str]=None, temperature: float=0.0, model: str = LLM_MODEL) -> str:
    if not _HAVE_GENAI:
        raise LLMNotConfigured("google-genai not installed.")
    client = init_llm_client(required=True)
    combined = f"{system}\n\n{prompt}" if system else prompt
    cfg = types.GenerateContentConfig(temperature=temperature, response_mime_type="application/json") if types else None
    resp = generate_content(client, contents=combined, config=cfg, model=model)
    text = getattr(resp, "text", None) or getattr(resp, "output_text", None) or ""
    if not isinstance(text, str):
        raise LLMCallError("LLM returned non-string content for JSON response.")
    return text
