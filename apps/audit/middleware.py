from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from .utils import log_event

DEFAULT_IGNORED_PREFIXES = (
    "/static/", "/media/", "/favicon.ico",
    "/api/schema", "/api/docs",
    "/admin", "/admin/login", "/admin/js/", "/admin/css/", "/admin/img/",
)


class AuditRequestMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        if not getattr(settings, "AUDIT_ENABLED", True):
            return response
        if not getattr(settings, "AUDIT_LOG_HTTP", False):
            return response

        try:
            path = request.path or ""
            ignored = getattr(settings, "AUDIT_IGNORED_PATHS", DEFAULT_IGNORED_PREFIXES)
            if any(path.startswith(p) for p in ignored):
                return response

            user = getattr(request, "user", None)
            ip = request.META.get("HTTP_X_FORWARDED_FOR") or request.META.get("REMOTE_ADDR")
            ua = request.META.get("HTTP_USER_AGENT", "")

            # логируем как VIEW; object_type = HTTP <METHOD> <PATH>
            log_event(
                actor=user if getattr(user, "is_authenticated", False) else None,
                action="VIEW",
                object_type=f"HTTP {request.method}",
                object_id=None,
                diff_json={"path": path, "status": int(getattr(response, "status_code", 0))},
                ip=ip, user_agent=ua,
            )
        except Exception:
            pass
        return response
