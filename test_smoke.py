import io
import math
import wave
import time
import struct
import pytest
from fastapi.testclient import TestClient
from paho.mqtt import client as mqtt

from src.main import app
from src.config import settings

client = TestClient(app)


def generate_beep_wav(duration=1.5, freq=440.0, sample_rate=16000) -> bytes:
    """Генерирует валидный WAV-файл со звуком определенной частоты (синусоида)."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)

        for i in range(int(sample_rate * duration)):
            value = int(32767.0 * math.sin(freq * math.pi * 2 * i / sample_rate))
            data = struct.pack("<h", value)
            wav_file.writeframesraw(data)

    buffer.seek(0)
    return buffer.read()


def test_full_pipeline_smoke():
    """
    Интеграционный Smoke-тест.
    Проверяет всю цепочку: API -> librosa -> Whisper -> отправка в MQTT -> доставка брокером.
    """
    received_messages = []

    def on_message(client, userdata, msg):
        received_messages.append(msg.payload.decode("utf-8"))

    test_mqtt = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2, protocol=mqtt.MQTTv5
    )
    test_mqtt.on_message = on_message

    test_mqtt.connect(settings.broker_url, settings.broker_port, 60)

    test_device_id = 9999
    topic = f"machinist_esp/{test_device_id}"
    test_mqtt.subscribe(topic, qos=2)
    test_mqtt.loop_start()

    try:

        wav_bytes = generate_beep_wav(duration=1.5)
        files = {"file": ("smoke_test.wav", wav_bytes, "audio/wav")}
        data = {"id": test_device_id}

        response = client.post("/transcribe", data=data, files=files)

        assert response.status_code == 200, f"API вернул ошибку: {response.text}"
        json_response = response.json()
        assert "text" in json_response

        transcribed_text = json_response["text"]
        print(f"\n[Smoke] Whisper распознал: '{transcribed_text}'")

        timeout = 7
        start_time = time.time()
        while not received_messages and (time.time() - start_time) < timeout:
            time.sleep(0.5)

        assert (
            len(received_messages) > 0
        ), "Критический сбой: сообщение не дошло до MQTT брокера!"

        assert (
            received_messages[0] == transcribed_text
        ), "Текст в MQTT не совпадает с ответом API"

    finally:

        test_mqtt.loop_stop()
        test_mqtt.disconnect()
