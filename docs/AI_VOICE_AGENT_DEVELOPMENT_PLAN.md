# KẾ HOẠCH PHÁT TRIỂN HỆ THỐNG AI VOICE AGENT TỰ ĐỘNG GỌI API (PYTHON FASTAPI)

> **Dự án**: `automatic-calling-api`  
> **Ngôn ngữ & Framework**: **Python 3.13 + FastAPI + Pydantic v2**  
> **Hệ thống backend đích**: VN Doctor (`health-records` và `care-requests`)  
> **Đối tượng người dùng**: Bệnh nhân sử dụng Mobile App (App Account)  
> **Mô hình kiến trúc**: Client-side STT/TTS + AI Server Slot-Filling & LLM Tool-Calling  

---

## 1. TỔNG QUAN VÀ MỤC TIÊU DỰ ÁN

### 1.1. Mục tiêu
Xây dựng một dịch vụ trung gian thông minh (**AI Agent Server bằng Python**) tiếp nhận câu lệnh bằng giọng nói (đã được ứng dụng di động chuyển thành văn bản - STT) từ bệnh nhân, phân tích ngữ nghĩa để:
1. **Nhận diện ý định (Intent)**:
   - Ghi nhận chỉ số sức khỏe cá nhân (`health-records`).
   - Tạo phiếu yêu cầu hỗ trợ chăm sóc y tế (`care-requests`).
2. **Trích xuất thông tin (Slot Extraction)**:
   - Bóc tách các tham số đo lường (chỉ số huyết áp, đường huyết, nhịp tim...) hoặc triệu chứng bệnh.
3. **Kiểm tra tính đầy đủ (Slot Filling & Multi-turn)**:
   - Nếu **thiếu thông tin**: Duy trì trạng thái phiên (`session_id`) và phản hồi câu hỏi thoại gợi mở tự nhiên để ứng dụng hỏi lại bệnh nhân.
   - Nếu **đủ thông tin**: Chuẩn hóa payload Pydantic và tự động gọi API Backend của hệ thống VN Doctor bằng chính **JWT Bearer Token** của bệnh nhân.

---

## 2. KIẾN TRÚC TỔNG THỂ (SYSTEM ARCHITECTURE)

```
[Bệnh nhân nói tiếng Việt]
          │
          ▼
   [Mobile App]
   ├── 1. Thu âm & Nhận diện giọng nói (Native STT: iOS SFSpeechRecognizer / Android SpeechRecognizer)
   ├── 2. Hiển thị chữ chạy Real-time trên màn hình để bệnh nhân kiểm tra
   └── 3. Gửi Request lên AI Server kèm User Token & Session ID
          │
          ▼  POST /api/v1/voice-command/process (Authorization: Bearer <UserToken>)
   ┌─────────────────────────────────────────────────────────────────────────────┐
   │ AI SERVER (Python FastAPI - automatic-calling-api)                          │
   │                                                                             │
   │  ┌────────────────────────┐        ┌─────────────────────────────────────┐  │
   │  │ Session Store (Memory/ │ ◄────► │ Conversation & Slot Filling Manager │  │
   │  │ Redis cache)           │        └──────────────────┬──────────────────┘  │
   │  └────────────────────────┘                           │                     │
   │                                                       ▼                     │
   │                            ┌─────────────────────────────────────┐          │
   │                            │ LLM Engine (OpenAI / Gemini Flash)  │          │
   │                            │ Function Calling & Pydantic Schema  │          │
   │                            └──────────────────┬──────────────────┘          │
   │                                               │                             │
   │                  ┌────────────────────────────┴──────────────────────────┐  │
   │                  ▼                                                       ▼  │
   │        [Còn thiếu trường]                                          [Đủ trường]│
   │         Trả về câu hỏi thoại                                             │  │
   │         để App hỏi tiếp                                                  │  │
   └──────────────────┬───────────────────────────────────────────────────────┼──┘
                      │                                                       │
                      │                                    HTTPX Client kèm   │
                      │                                    User Bearer Token  │
                      ▼                                                       ▼
                [Mobile App]                                       [VN Doctor Backend]
             Bật TTS đọc câu hỏi                                   POST /health-records
             cho bệnh nhân nghe                                    POST /care-requests
```

---

## 3. PHÂN TÍCH 2 API ĐÍCH TỪ PHÍA BỆNH NHÂN (VN DOCTOR BE)

### 3.1. API Tạo bản ghi chỉ số sức khỏe
* **Endpoint**: `POST /health-records`
* **Xác thực**: `@UseGuards(CombinedAuthGuard)` với JWT Token của tài khoản App (`user.type === 'APP_ACCOUNT'`).
* **Các trường dữ liệu**:
  | Trường | Kiểu | Bắt buộc | AI Xử lý & Tự động ánh xạ |
  |---|---|:---:|---|
  | `healthProfileId` | UUID | **Có** | Lấy từ Context gửi kèm của App hoặc lấy Profile mặc định của bệnh nhân. |
  | `metricType` | Enum | **Có** | 1 trong 8 loại: `BLOOD_PRESSURE`, `BLOOD_GLUCOSE`, `HEART_RATE`, `SPO2`, `TEMPERATURE`, `WEIGHT`, `HEIGHT`, `BMI`. |
  | `valueNumeric` | Float | **Có** | Trích xuất từ số đo người bệnh đọc (huyết áp tâm thu, đường huyết, cân nặng...). |
  | `secondaryValue` | Float | Không | Trích xuất huyết áp tâm trương (khi là `BLOOD_PRESSURE`). |
  | `unit` | String | **Có** | **AI tự động điền đơn vị chuẩn**: `mmHg`, `mmol/L`, `bpm`, `%`, `°C`, `kg`, `cm`. |
  | `note` | String | Không | Ghi chú hoàn cảnh (vd: *"đo lúc đói"*, *"sau ăn 2 tiếng"*). |
  | `measuredAt` | Datetime | Không | Mặc định thời gian hiện tại nếu không nói khác. |

### 3.2. API Tạo phiếu yêu cầu chăm sóc y tế
* **Endpoint**: `POST /care-requests`
* **Xác thực**: `@UseGuards(AppAuthGuard)` với JWT Token của tài khoản App. BE lấy trực tiếp `account.id`.
* **Các trường dữ liệu**:
  | Trường | Kiểu | Bắt buộc | AI Xử lý & Tự động ánh xạ |
  |---|---|:---:|---|
  | `subscriptionId` | UUID | **Có** | ID gói chăm sóc `ACTIVE`. Lấy từ context của App hoặc AI Server tra cứu qua BE. |
  | `title` | String | **Có** | Tóm tắt triệu chứng ngắn gọn từ 5 - 255 ký tự (vd: *"Cảm thấy chóng mặt buồn nôn sau khi uống thuốc"*). |
  | `description` | String | Không | Toàn bộ mô tả chi tiết của bệnh nhân về triệu chứng, tiền sử. |
  | `mediaUrls` | List[str] | Không | Danh sách URL hình ảnh đính kèm (nếu app có truyền). |

---

## 4. THIẾT KẾ GIAO DIỆN API (API CONTRACTS GIỮA APP VÀ AI SERVER)

### 4.1. Endpoint chính: Tiếp nhận câu lệnh thoại
* **Method**: `POST /api/v1/voice-command/process`
* **Headers**: `Authorization: Bearer <User_JWT_Token>`
* **Request Body**:
```json
{
  "session_id": "sess_patient_123",
  "transcript": "Sáng nay tôi vừa đo huyết áp được 130 trên 85",
  "context": {
    "health_profile_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
    "subscription_id": "b1ffbc88-8b0a-3ef7-aa5c-5aa8ad270b22"
  }
}
```

### 4.2. Response Trạng thái 1: Cần hỏi thêm thông tin (Slot Missing)
```json
{
  "status": "NEED_MORE_INFO",
  "session_id": "sess_patient_123",
  "intent": "create_health_record",
  "collected_data": {
    "metric_type": "BLOOD_PRESSURE"
  },
  "missing_fields": ["value_numeric"],
  "response_message": "Bác vừa đo chỉ số huyết áp được bao nhiêu ạ? Ví dụ như một trăm hai mươi trên tám mươi."
}
```

### 4.3. Response Trạng thái 2: Đã đủ thông tin & Đã gọi API BE thành công
```json
{
  "status": "SUCCESS",
  "session_id": "sess_patient_123",
  "intent": "create_health_record",
  "response_message": "Đã ghi nhận chỉ số huyết áp 130/85 mmHg vào hồ sơ sức khỏe thành công.",
  "data": {
    "id": "rec_9999",
    "metricType": "BLOOD_PRESSURE",
    "valueNumeric": 130,
    "secondaryValue": 85,
    "unit": "mmHg"
  }
}
```

---

## 5. CẤU TRÚC DỰ ÁN PYTHON (FASTAPI)

```text
automatic-calling-api/
├── app/
│   ├── api/
│   │   └── v1/
│   │       └── endpoints/
│   │           └── voice.py         # Router POST /api/v1/voice-command/process
│   ├── core/
│   │   ├── config.py                # Pydantic Settings đọc .env
│   │   └── security.py              # Xử lý Bearer Token forwarding
│   ├── schemas/
│   │   ├── voice.py                 # Request/Response schemas của Voice API
│   │   ├── health_record.py         # Schemas DTO khớp với BE VN Doctor
│   │   └── care_request.py          # Schemas DTO khớp với BE VN Doctor
│   ├── services/
│   │   ├── ai_engine.py             # Gọi LLM (OpenAI/Gemini) với Tool Calling
│   │   ├── session_manager.py       # Quản lý phiên hội thoại & lưu slots dở
│   │   └── vndoctor_client.py       # HTTPX Client gọi sang BE VN Doctor
│   └── main.py                      # FastAPI Application entrypoint
├── requirements.txt
├── .env.example
└── README.md
```

---

## 6. KẾ HOẠCH TRIỂN KHAI CHI TIẾT THEO TỪNG ĐẦU MỤC (ROADMAP)

### 📌 ĐẦU MỤC 1: KHỞI TẠO DỰ ÁN & MÔI TRƯỜNG PYTHON
* **Thư viện chính (`requirements.txt`)**:
  - `fastapi`, `uvicorn[standard]`
  - `pydantic`, `pydantic-settings`
  - `httpx` (async HTTP client)
  - `openai` hoặc `google-genai` (SDK LLM)
  - `python-dotenv`
* **Công việc cụ thể**:
  1. Tạo Virtual Environment (`venv`).
  2. Tạo cấu trúc thư mục `app/` như trên.
  3. Cấu hình biến môi trường (`.env`):
     - `VN_DOCTOR_API_BASE_URL=https://api-navi-doctor.tomotek.vn/api`
     - `OPENAI_API_KEY=...` (hoặc `GEMINI_API_KEY=...`)
     - `LLM_MODEL=gpt-4o-mini` (hoặc `gemini-2.0-flash`)

---

### 📌 ĐẦU MỤC 2: XÂY DỰNG LLM ENGINE (TOOL CALLING & EXTRACTOR)
* **Nhiệm vụ cụ thể**:
  1. **Định nghĩa Pydantic Schemas làm Tools**:
     - `HealthRecordExtraction`: `metric_type`, `value_numeric`, `secondary_value`, `unit`, `note`.
     - `CareRequestExtraction`: `title`, `description`.
  2. **System Prompt chuyên biệt tiếng Việt y tế**:
     - Nhận diện cách nói số đo của người Việt ("120 trên 80", "đường huyết 6 chấm 5", "sốt 38 độ rưỡi").
     - Tự động map đơn vị chuẩn y khoa (`mmHg`, `mmol/L`, `bpm`, `°C`, `kg`).
  3. **Output Parser**: Trả về kết quả có cấu trúc JSON chính xác.

---

### 📌 ĐẦU MỤC 3: QUẢN LÝ PHIÊN HỘI THOẠI & SLOT FILLING
* **Nhiệm vụ cụ thể**:
  1. **`SessionManager`**:
     - Lưu trữ trạng thái theo `session_id` trong Memory Cache (hoặc Redis).
     - Lưu các trường đã thu thập được (`collected_slots`).
  2. **Bộ kiểm tra thiếu trường (Slot Validator)**:
     - So khớp các trường đã có với danh sách trường bắt buộc.
     - Khi người bệnh nói câu bổ sung ở lượt sau (vd: *"Là 120 trên 80 nhé"*), tự động merge vào slot trước đó.
  3. **Sinh câu hỏi thoại tự nhiên**:
     - Tạo câu hỏi ngắn gọn, lễ phép, phù hợp cho người lớn tuổi.

---

### 📌 ĐẦU MỤC 4: CLIENT GỌI SANG BE VN DOCTOR (HTTPX)
* **Nhiệm vụ cụ thể**:
  1. **`VnDoctorClient`**:
     - `POST /health-records`: Chuyển đổi payload Pydantic sang đúng camelCase format mà NestJS BE yêu cầu (`healthProfileId`, `valueNumeric`, `metricType`...).
     - `POST /care-requests`: Gửi `subscriptionId`, `title`, `description`.
  2. **Chuyển tiếp User Token**:
     - Gắn header `Authorization: Bearer <token>` của bệnh nhân.
  3. **Xử lý lỗi**:
     - Bắt mã lỗi 400, 401, 403, 500 từ BE và map thành thông báo thân thiện.

---

### 📌 ĐẦU MỤC 5: HƯỚNG DẪN TÍCH HỢP PHÍA MOBILE APP
* **Nhiệm vụ phía Mobile App**:
  1. **Voice Input (STT)**:
     - Thu âm và hiển thị chữ trực tiếp trên giao diện màn hình.
  2. **Gửi Request**:
     - Bệnh nhân nói xong -> App gọi `POST /api/v1/voice-command/process`.
  3. **Nhận kết quả**:
     - `NEED_MORE_INFO`: Bật Text-To-Speech của điện thoại đọc câu hỏi lên và mở lại micro.
     - `SUCCESS`: Đọc thông báo thành công và hiển thị card kết quả.
