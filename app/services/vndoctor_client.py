import sys
import httpx
from typing import Dict, Any, Optional
from fastapi import HTTPException
from app.core.config import settings
from app.schemas.health_record import CreateHealthRecordPayload
from app.schemas.care_request import CreateCareRequestPayload

def safe_print(msg: str):
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", errors="backslashreplace").decode("ascii"))

class VnDoctorClient:
    """
    Client bất đồng bộ kết nối trực tiếp sang Backend của VN Doctor.
    Chuyển tiếp (forward) nguyên vẹn Bearer Token của Bệnh nhân.
    """
    def __init__(self):
        self.base_url = settings.VN_DOCTOR_API_BASE_URL.rstrip('/')

    def _get_headers(self, token: str) -> Dict[str, str]:
        clean_token = token.replace("Bearer ", "").strip()
        return {
            "Authorization": f"Bearer {clean_token}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    async def create_health_record(self, token: str, payload: CreateHealthRecordPayload) -> Dict[str, Any]:
        """
        Gọi POST /health-records trên BE VN Doctor
        """
        url = f"{self.base_url}/health-records"
        body = payload.model_dump(by_alias=True, exclude_none=True)
        headers = self._get_headers(token)
        
        async with httpx.AsyncClient(timeout=15.0, verify=False, follow_redirects=True) as client:
            try:
                safe_print(f"[VnDoctorClient] POST {url}")
                safe_print(f"[VnDoctorClient] Body: {body}")
                response = await client.post(url, json=body, headers=headers)
                safe_print(f"[VnDoctorClient] Status Code: {response.status_code}")
                safe_print(f"[VnDoctorClient] Response: {response.text}")
                if response.status_code >= 400:
                    error_data = response.json() if "application/json" in response.headers.get("content-type", "") else response.text
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"Lỗi từ BE VN Doctor: {error_data}"
                    )
                return response.json()
            except httpx.RequestError as e:
                safe_print(f"[ERROR] [VnDoctorClient] Lỗi kết nối BE VN Doctor: {type(e).__name__} - {str(e)}")
                raise HTTPException(
                    status_code=502,
                    detail=f"Không thể kết nối tới Backend VN Doctor ({url}): {str(e)}"
                )

    async def create_care_request(self, token: str, payload: CreateCareRequestPayload) -> Dict[str, Any]:
        """
        Gọi POST /care-requests trên BE VN Doctor
        """
        url = f"{self.base_url}/care-requests"
        body = payload.model_dump(exclude_none=True)
        
        async with httpx.AsyncClient(timeout=15.0, verify=False, follow_redirects=True) as client:
            try:
                headers = self._get_headers(token)
                safe_print(f"[VnDoctorClient] POST {url}")
                safe_print(f"[VnDoctorClient] Body: {body}")
                response = await client.post(url, json=body, headers=headers)
                safe_print(f"[VnDoctorClient] Status Code: {response.status_code}")
                safe_print(f"[VnDoctorClient] Response: {response.text}")
                if response.status_code >= 400:
                    error_data = response.json() if "application/json" in response.headers.get("content-type", "") else response.text
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"Lỗi từ BE VN Doctor: {error_data}"
                    )
                return response.json()
            except httpx.RequestError as e:
                safe_print(f"[ERROR] [VnDoctorClient] Lỗi kết nối BE VN Doctor: {type(e).__name__} - {str(e)}")
                raise HTTPException(
                    status_code=502,
                    detail=f"Không thể kết nối tới Backend VN Doctor ({url}): {str(e)}"
                )

    async def get_active_subscription_id(self, token: str) -> Optional[str]:
        """
        Hỗ trợ tự động tra cứu gói ACTIVE nếu App chưa gửi subscriptionId lên.
        """
        url = f"{self.base_url}/care-subscriptions/my-subscriptions"
        async with httpx.AsyncClient(timeout=10.0, verify=False, follow_redirects=True) as client:
            try:
                res = await client.get(url, headers=self._get_headers(token), params={"status": "ACTIVE"})
                if res.status_code == 200:
                    items = res.json()
                    if isinstance(items, list) and len(items) > 0:
                        return items[0].get("id")
                    elif isinstance(items, dict) and "data" in items and len(items["data"]) > 0:
                        return items["data"][0].get("id")
            except Exception:
                pass
        return None

vndoctor_client = VnDoctorClient()
