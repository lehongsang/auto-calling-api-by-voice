# Automatic Calling API (AI Voice Agent Server)

Hệ thống AI Agent hỗ trợ bệnh nhân tự động gọi API ghi nhận chỉ số sức khỏe (`health-records`) và phiếu yêu cầu chăm sóc y tế (`care-requests`) qua giọng nói.

## 🚀 Khởi chạy dự án

### 1. Kích hoạt môi trường ảo:
```bash
# Windows PowerShell:
.\venv\Scripts\Activate.ps1

# Hoặc CMD:
.\venv\Scripts\activate.bat
```

### 2. Cài đặt thư viện (nếu chưa cài):
```bash
pip install -r requirements.txt
```

### 3. Cấu hình file `.env`:
Sao chép từ `.env.example` và chỉnh sửa:
```env
VN_DOCTOR_API_BASE_URL=http://localhost:3000
AI_PROVIDER=OPENAI
OPENAI_API_KEY=sk-... (nếu có)
```
*(Nếu chưa có API Key, hệ thống tự động kích hoạt Rule-based Parser thông minh để phục vụ việc test).*

### 4. Chạy server:
```bash
uvicorn app.main:app --reload --port 8000
```

### 5. Truy cập Swagger UI:
Mở trình duyệt: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🧪 Ví dụ Test API qua cURL

### 1. Test Ghi nhận huyết áp (Hỏi thêm nếu thiếu số đo)
```bash
curl -X POST "http://localhost:8000/api/v1/voice-command/process" \
  -H "Authorization: Bearer mock_jwt_token_user_123" \
  -H "Content-Type: application/json" \
  -d '{
    "transcript": "Tôi vừa đo huyết áp xong"
  }'
```
*Kết quả trả về*: `NEED_MORE_INFO` ("Bác vừa đo chỉ số huyết áp được bao nhiêu ạ?")

### 2. Bệnh nhân trả lời tiếp (Slot-filling hoàn tất)
```bash
curl -X POST "http://localhost:8000/api/v1/voice-command/process" \
  -H "Authorization: Bearer mock_jwt_token_user_123" \
  -H "Content-Type: application/json" \
  -d '{
    "transcript": "Một trăm hai mươi trên tám mươi",
    "context": {
      "health_profile_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"
    }
  }'
```
*Kết quả trả về*: `SUCCESS` (Đã gọi BE `POST /health-records` lưu 120/80 mmHg).

---

## 📱 Tài liệu Tích hợp dành cho Mobile App
* Chi tiết cách gọi API, quản lý phiên đa lượt (Multi-turn Slot Filling), xử lý TTS và Code mẫu Flutter/React Native: Xem tại **[docs/MOBILE_APP_INTEGRATION_GUIDE.md](docs/MOBILE_APP_INTEGRATION_GUIDE.md)**.

