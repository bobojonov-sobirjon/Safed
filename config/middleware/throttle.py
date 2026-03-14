"""
Rate limiting middleware for API protection.
"""
import time
from typing import Dict, Tuple
from django.conf import settings
from django.http import JsonResponse, HttpRequest


class RateLimitMiddleware:
    """
    Simple in-memory rate limiting middleware.
    For production, use Redis-based solution.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.cache: Dict[str, Tuple[int, float]] = {}
        self.enabled = getattr(settings, 'RATE_LIMIT_ENABLE', True)
        self.max_requests = getattr(settings, 'RATE_LIMIT_REQUESTS', 100)
        self.window = getattr(settings, 'RATE_LIMIT_WINDOW', 60)
    
    def __call__(self, request: HttpRequest):
        if not self.enabled:
            return self.get_response(request)
        
        if request.path.startswith('/admin/') or request.path.startswith('/static/'):
            return self.get_response(request)
        
        client_ip = self._get_client_ip(request)
        current_time = time.time()
        
        if client_ip in self.cache:
            requests, window_start = self.cache[client_ip]
            
            if current_time - window_start > self.window:
                self.cache[client_ip] = (1, current_time)
            else:
                if requests >= self.max_requests:
                    return JsonResponse(
                        {
                            'detail': 'Слишком много запросов. Попробуйте позже.',
                            'retry_after': int(self.window - (current_time - window_start)),
                        },
                        status=429
                    )
                self.cache[client_ip] = (requests + 1, window_start)
        else:
            self.cache[client_ip] = (1, current_time)
        
        self._cleanup_old_entries(current_time)
        
        return self.get_response(request)
    
    def _get_client_ip(self, request: HttpRequest) -> str:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', 'unknown')
    
    def _cleanup_old_entries(self, current_time: float):
        if len(self.cache) > 10000:
            expired_keys = [
                key for key, (_, window_start) in self.cache.items()
                if current_time - window_start > self.window * 2
            ]
            for key in expired_keys:
                del self.cache[key]
