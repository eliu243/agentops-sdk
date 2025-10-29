"""
HTTP A2A monitoring for requests and httpx libraries.
"""
import time
import json
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from ..transport import post_event
from ..runtime import current_run_id
from ..config import config
from ..policy import evaluate


def _extract_service_name(url: str) -> str:
    """Extract a clean service name from URL."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        # Remove common prefixes/suffixes
        domain = domain.replace('www.', '').replace('api.', '')
        
        # Handle common services
        if 'stripe.com' in domain:
            return 'stripe'
        elif 'openai.com' in domain:
            return 'openai'
        elif 'anthropic.com' in domain:
            return 'anthropic'
        elif 'googleapis.com' in domain:
            return 'google_apis'
        elif 'amazonaws.com' in domain:
            return 'aws'
        elif 'internal' in domain or 'localhost' in domain:
            return f'internal_{parsed.hostname}'
        else:
            # Use the main domain
            return domain.split('.')[0] if '.' in domain else domain
    except Exception:
        return 'unknown_service'


def _safe_serialize(data: Any, max_length: int = 1000) -> Optional[str]:
    """Safely serialize data with length limits."""
    try:
        if data is None:
            return None
        
        # Convert to string representation
        if isinstance(data, (dict, list)):
            serialized = json.dumps(data, default=str)
        else:
            serialized = str(data)
        
        # Truncate if too long
        if len(serialized) > max_length:
            serialized = serialized[:max_length] + "...[truncated]"
        
        return serialized
    except Exception:
        return "[unable to serialize]"


def _log_http_call(
    method: str,
    url: str,
    request_data: Any = None,
    response_data: Any = None,
    status_code: Optional[int] = None,
    duration_ms: float = 0,
    error: Optional[str] = None
):
    """Log an HTTP A2A communication event."""
    run_id = current_run_id()
    if not run_id:
        return  # No active run
    
    service_name = _extract_service_name(url)
    
    event_data = {
        "run_id": run_id,
        "type": "a2a_http_call",
        "method": method.upper(),
        "url": url,
        "service_name": service_name,
        "request_data": _safe_serialize(request_data),
        "response_data": _safe_serialize(response_data),
        "status_code": status_code,
        "duration_ms": round(duration_ms, 2),
        "error": error,
        "created_at": int(time.time() * 1000)
    }
    
    # Send event asynchronously (best effort)
    try:
        post_event(event_data)
    except Exception:
        pass  # Don't break the user's code if monitoring fails


def _evaluate_and_maybe_block(url: str, request_data: Any) -> None:
    """Apply egress policy; log and optionally block."""
    try:
        text = None
        if isinstance(request_data, (str, bytes)):
            text = request_data.decode("utf-8", "ignore") if isinstance(request_data, bytes) else request_data
        elif isinstance(request_data, dict):
            # Avoid dumping secrets; stringify compactly
            text = json.dumps(request_data, default=str)
        elif request_data is not None:
            text = str(request_data)

        result = evaluate(text, direction="egress", extra_forbidden=config.forbidden_patterns)
        if not result.allowed:
            # Log guardrail violation as an A2A event
            post_event(
                {
                    "run_id": current_run_id(),
                    "type": "a2a_guardrail_violation",
                    "method": "EGRESS",
                    "url": url,
                    "service_name": "guardrail",
                    "request_data": _safe_serialize(text),
                    "response_data": None,
                    "status_code": 0,
                    "duration_ms": 0,
                    "error": f"{result.label}:{result.reason}:{','.join(result.matches)[:180]}",
                    "created_at": int(time.time() * 1000),
                }
            )
            if config.block_on_violation:
                raise RuntimeError("Egress blocked by policy: unauthorized content detected")
    except Exception:
        # Do not break if policy evaluation fails; only block on explicit decision
        if config.block_on_violation:
            raise


def patch_requests():
    """Patch the requests library for HTTP monitoring."""
    try:
        import requests
        
        # Store original methods
        original_get = requests.get
        original_post = requests.post
        original_put = requests.put
        original_delete = requests.delete
        original_patch = requests.patch
        
        def make_wrapper(original_method, method_name):
            def wrapper(*args, **kwargs):
                start_time = time.time()
                url = args[0] if args else kwargs.get('url', '')
                request_data = kwargs.get('data') or kwargs.get('json')
                
                try:
                    # Egress policy check before sending
                    _evaluate_and_maybe_block(url, request_data)

                    # Make the actual request
                    response = original_method(*args, **kwargs)
                    
                    # Log successful request
                    _log_http_call(
                        method=method_name,
                        url=url,
                        request_data=request_data,
                        response_data=response.text,
                        status_code=response.status_code,
                        duration_ms=(time.time() - start_time) * 1000
                    )
                    
                    return response
                    
                except Exception as e:
                    # Log failed request
                    _log_http_call(
                        method=method_name,
                        url=url,
                        request_data=request_data,
                        error=str(e),
                        duration_ms=(time.time() - start_time) * 1000
                    )
                    raise
            
            return wrapper
        
        # Apply patches
        requests.get = make_wrapper(original_get, 'GET')
        requests.post = make_wrapper(original_post, 'POST')
        requests.put = make_wrapper(original_put, 'PUT')
        requests.delete = make_wrapper(original_delete, 'DELETE')
        requests.patch = make_wrapper(original_patch, 'PATCH')
        
    except ImportError:
        pass  # requests not installed


def patch_httpx():
    """Patch the httpx library for HTTP monitoring."""
    try:
        import httpx
        
        # Store original methods
        original_get = httpx.get
        original_post = httpx.post
        original_put = httpx.put
        original_delete = httpx.delete
        original_patch = httpx.patch
        
        def make_wrapper(original_method, method_name):
            def wrapper(*args, **kwargs):
                start_time = time.time()
                url = args[0] if args else kwargs.get('url', '')
                request_data = kwargs.get('data') or kwargs.get('json')
                
                try:
                    # Egress policy check before sending
                    _evaluate_and_maybe_block(url, request_data)

                    # Make the actual request
                    response = original_method(*args, **kwargs)
                    
                    # Log successful request
                    _log_http_call(
                        method=method_name,
                        url=url,
                        request_data=request_data,
                        response_data=response.text,
                        status_code=response.status_code,
                        duration_ms=(time.time() - start_time) * 1000
                    )
                    
                    return response
                    
                except Exception as e:
                    # Log failed request
                    _log_http_call(
                        method=method_name,
                        url=url,
                        request_data=request_data,
                        error=str(e),
                        duration_ms=(time.time() - start_time) * 1000
                    )
                    raise
            
            return wrapper
        
        # Apply patches
        httpx.get = make_wrapper(original_get, 'GET')
        httpx.post = make_wrapper(original_post, 'POST')
        httpx.put = make_wrapper(original_put, 'PUT')
        httpx.delete = make_wrapper(original_delete, 'DELETE')
        httpx.patch = make_wrapper(original_patch, 'PATCH')
        
    except ImportError:
        pass  # httpx not installed


def patch_http_libraries():
    """Patch all HTTP libraries for A2A monitoring."""
    patch_requests()
    patch_httpx()
