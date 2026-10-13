import jwt
from typing import Optional
from fastapi import HTTPException, status

def extract_account_id_from_token(token: str) -> str:
    """
    Giải mã JWT token của VN Doctor để lấy id tài khoản người bệnh.
    Không verify secret ở đây vì AI Server chỉ forward token sang BE VN Doctor.
    """
    try:
        # Bỏ qua xác thực chữ ký để lấy payload nhanh chóng
        payload = jwt.decode(token, options={"verify_signature": False})
        
        # Thử lấy các trường id thông dụng của VN Doctor JWT
        account_id = payload.get("id") or payload.get("sub") or payload.get("accountId")
        if not account_id and isinstance(payload.get("account"), dict):
            account_id = payload.get("account", {}).get("id")
            
        if not account_id:
            # Fallback lấy hash của token nếu payload không chứa id rõ ràng
            account_id = f"user_{abs(hash(token)) % 10000000}"
            
        return str(account_id)
    except Exception as e:
        # Nếu token không giải mã được, fallback dùng hash chuỗi
        return f"user_{abs(hash(token)) % 10000000}"
