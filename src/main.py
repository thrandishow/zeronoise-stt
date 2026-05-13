from fastapi.middleware.cors import CORSMiddleware
from fastapi import (
    FastAPI,
    UploadFile,
    File,
    HTTPException,
    Form,
)
from fastapi.concurrency import run_in_threadpool
import whisper
import warnings
from src.utils.audio_utils import transcribe_audio
from src.utils.mqtt import mqtt_client, send_message_mqtt
from src.config import logger

warnings.filterwarnings("ignore")
# TODO: вынести логику из main.py в отдельные services
app = FastAPI(
    title="Russian Speech-to-Text API",
    description="API для распознавания русской речи с использованием Whisper",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
model = whisper.load_model("turbo")

logger.info("Model was uploaded successfully")

logger.info("MQTT client is running")


@app.post("/topics/{id}/{message}")
def send_message_endpoint(id: int, message: str):
    """
    Тестовый endpoint!!!
    Отправляет сообщение в MQTT-топик для конкретного устройства.

    Эндпоинт принимает идентификатор устройства и текстовое сообщение через URL-параметры,
    публикует их в MQTT-брокер с гарантией доставки (QoS=2).

    """
    try:
        mqtt_client.publish(topic=f"machinist_esp/{id}", payload=message, qos=2)
    except:
        raise HTTPException(status_code=400, detail="Wrong data for request")


@app.post("/transcribe")
async def transcribe_endpoint(id: int = Form(...), file: UploadFile = File(...)):
    """
    Эндпоинт для распознования русской речи.

    Принимает аудиофайл в любом формате (mp3, wav, m4a и т.д.)
    Возвращает распознанный текст, отправляет по MQTT
    """
    if not file.content_type.startswith("audio/"):
        raise HTTPException(status_code=415, detail="Invalid format")

    try:
        file_content = await file.read()
        transcription_text = await run_in_threadpool(
            transcribe_audio, file_content, model
        )

        try:
            send_message_mqtt(mqtt_client, id, transcription_text)
        except Exception as mqtt_error:
            logger.error(f"MQTT sending failed: {mqtt_error}")
            raise HTTPException(status_code=500, detail="MQTT sending failed")

        logger.info(f"Task finished for device {id} with message: {transcription_text}")
        return {"text": transcription_text}

    except Exception as e:
        error_detail = f"Transcription endpoint error: {str(e)}"
        logger.error(error_detail)
        raise HTTPException(status_code=500, detail=error_detail)


@app.get("/")
async def root():
    """Главная страница с информацией о сервисе"""
    return {
        "service": "Russian Speech-to-Text API",
        "version": "1.0.0",
        "documentation": "/docs",
    }
