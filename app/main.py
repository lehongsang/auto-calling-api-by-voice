from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.endpoints.voice import router as voice_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="AI Server hỗ trợ Bệnh nhân tự động gọi API ghi nhận chỉ số sức khỏe và phiếu yêu cầu chăm sóc y tế bằng giọng nói.",
    version="1.0.0",
    root_path=settings.ROOT_PATH,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Cấu hình CORS cho phép Mobile App và Web gọi tự do
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Router chính hiển thị trên Swagger: /voice-command/process
app.include_router(voice_router, prefix="")

# Alias tương thích ngược (ẩn khỏi Swagger để không bị trùng lặp)
app.include_router(voice_router, prefix="/api/v1", include_in_schema=False)
app.include_router(voice_router, prefix="/v1", include_in_schema=False)

@app.get("/", tags=["Health Check"])
@app.get("/health", tags=["Health Check"], include_in_schema=False)
async def root():
    docs_path = f"{settings.ROOT_PATH}/docs" if settings.ROOT_PATH else "/docs"
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "docs": docs_path
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.PORT, reload=True)
