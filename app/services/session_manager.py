import time
from typing import Optional, Dict, Any
from app.core.config import settings

class SessionManager:
    """
    Quản lý bộ nhớ phiên hội thoại (In-memory Cache với TTL).
    Hỗ trợ nhớ các slots đang thu thập dở dang của bệnh nhân.
    """
    def __init__(self):
        # Lưu trữ: { session_id: { "data": dict, "expires_at": float } }
        self._store: Dict[str, Dict[str, Any]] = {}

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        self._clean_expired()
        entry = self._store.get(session_id)
        if not entry:
            return None
        
        if time.time() > entry["expires_at"]:
            del self._store[session_id]
            return None
            
        # Gia hạn thời gian khi có tương tác mới
        entry["expires_at"] = time.time() + settings.SESSION_TTL_SECONDS
        return entry["data"]

    def save_session(self, session_id: str, data: Dict[str, Any]):
        self._store[session_id] = {
            "data": data,
            "expires_at": time.time() + settings.SESSION_TTL_SECONDS
        }

    def clear_session(self, session_id: str):
        if session_id in self._store:
            del self._store[session_id]

    def _clean_expired(self):
        now = time.time()
        expired_keys = [k for k, v in self._store.items() if now > v["expires_at"]]
        for k in expired_keys:
            del self._store[k]

session_manager = SessionManager()
