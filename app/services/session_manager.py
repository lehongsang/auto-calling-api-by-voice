import time
from typing import Optional, Dict, Any
from app.core.config import settings

# Thời gian chặn duplicate (giây) — trong khoảng này, cùng intent + title tương tự sẽ bị bỏ qua
DEDUP_WINDOW_SECONDS = 60

class SessionManager:
    """
    Quản lý bộ nhớ phiên hội thoại (In-memory Cache với TTL).
    Hỗ trợ nhớ các slots đang thu thập dở dang của bệnh nhân.
    Hỗ trợ chống duplicate API calls.
    """
    def __init__(self):
        # Lưu trữ: { session_id: { "data": dict, "expires_at": float } }
        self._store: Dict[str, Dict[str, Any]] = {}
        # Lưu trữ chống duplicate: { session_id: { "intent": str, "title_hash": str, "created_at": float } }
        self._recent_actions: Dict[str, Dict[str, Any]] = {}

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

    def is_duplicate_action(self, session_id: str, intent: str, title: str = "") -> bool:
        """
        Kiểm tra xem hành động này có bị trùng lặp trong khoảng DEDUP_WINDOW_SECONDS không.
        Chống trường hợp mic ghi lặp hoặc bệnh nhân nói 2 lần liên tiếp.
        """
        now = time.time()
        key = f"{session_id}_{intent}"
        entry = self._recent_actions.get(key)

        if entry:
            elapsed = now - entry["created_at"]
            if elapsed < DEDUP_WINDOW_SECONDS:
                # Cùng intent trong cửa sổ dedup → kiểm tra title có tương tự không
                if not title or entry.get("title_hash", "") == title[:30].lower():
                    return True

        return False

    def record_action(self, session_id: str, intent: str, title: str = ""):
        """Ghi nhận hành động vừa thực hiện để chống duplicate."""
        key = f"{session_id}_{intent}"
        self._recent_actions[key] = {
            "intent": intent,
            "title_hash": title[:30].lower() if title else "",
            "created_at": time.time()
        }

    def _clean_expired(self):
        now = time.time()
        # Dọn session hết hạn
        expired_keys = [k for k, v in self._store.items() if now > v["expires_at"]]
        for k in expired_keys:
            del self._store[k]

        # Dọn recent_actions cũ hơn DEDUP_WINDOW_SECONDS
        expired_actions = [k for k, v in self._recent_actions.items() if now - v["created_at"] > DEDUP_WINDOW_SECONDS]
        for k in expired_actions:
            del self._recent_actions[k]

session_manager = SessionManager()
