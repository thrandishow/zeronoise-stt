import sys
import io
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

mock_whisper = MagicMock()
sys.modules["whisper"] = mock_whisper

mock_mqtt = MagicMock()
sys.modules["paho.mqtt"] = mock_mqtt
sys.modules["paho.mqtt.client"] = mock_mqtt

from src.main import app
from src.utils.audio_utils import convert_audio_to_wav, transcribe_audio
from src.utils.mqtt import send_message_mqtt

client = TestClient(app)


@pytest.fixture
def mock_mqtt_client():
    """Фикстура для создания изолированного мока MQTT-клиента."""
    return MagicMock()


@pytest.fixture
def mock_ml_model():
    """Фикстура мока Whisper модели, которая всегда возвращает предсказуемый текст."""
    model = MagicMock()
    model.transcribe.return_value = {"text": "Тестовый распознанный текст"}
    return model


def test_root_endpoint():
    """Проверка доступности главной страницы и корректности JSON."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {
        "service": "Russian Speech-to-Text API",
        "version": "1.0.0",
        "documentation": "/docs",
    }


@patch("src.main.mqtt_client")
def test_send_message_endpoint(mock_main_mqtt_client):
    """Проверка тестового эндпоинта отправки сообщений."""
    response = client.post("/topics/123/hello_world")

    assert response.status_code == 200

    mock_main_mqtt_client.publish.assert_called_once_with(
        topic="machinist_esp/123", payload="hello_world", qos=2
    )


def test_transcribe_endpoint_invalid_file_type():
    """Проверка валидации формата файла (должно быть аудио)."""

    files = {"file": ("test.txt", b"some text data", "text/plain")}
    data = {"id": 1}

    response = client.post("/transcribe", data=data, files=files)

    assert response.status_code == 415
    assert response.json()["detail"] == "Invalid format"


@patch("src.main.send_message_mqtt")
@patch("src.main.transcribe_audio")
def test_transcribe_endpoint_success(mock_transcribe, mock_send_mqtt):
    """Успешный сценарий эндпоинта транскрибации с моками логики."""

    mock_transcribe.return_value = "Привет, как дела?"

    files = {"file": ("test.wav", b"fake_audio_bytes", "audio/wav")}
    data = {"id": 42}

    response = client.post("/transcribe", data=data, files=files)

    assert response.status_code == 200
    assert response.json() == {"text": "Привет, как дела?"}

    mock_transcribe.assert_called_once()
    mock_send_mqtt.assert_called_once()


@patch("src.utils.audio_utils.sf.write")
@patch("src.utils.audio_utils.librosa.load")
def test_convert_audio_to_wav(mock_librosa_load, mock_sf_write):
    """Тест конвертации аудио с подменой тяжелых аудио-операций."""
    mock_librosa_load.return_value = ([0.0, 0.1, -0.1], 16000)

    result = convert_audio_to_wav(b"dummy_bytes")

    mock_librosa_load.assert_called_once()
    mock_sf_write.assert_called_once()
    assert isinstance(result, bytes)


@patch("src.utils.audio_utils.convert_audio_to_wav")
@patch("src.utils.audio_utils.librosa.load")
def test_transcribe_audio_logic(mock_librosa_load, mock_convert, mock_ml_model):
    """Проверка бизнес-логики вызова модели Whisper."""
    mock_convert.return_value = b"wav_bytes"
    mock_librosa_load.return_value = ([0.1, 0.2], 16000)

    result = transcribe_audio(b"raw_bytes", mock_ml_model)

    assert result == "Тестовый распознанный текст"
    mock_convert.assert_called_once_with(b"raw_bytes")
    mock_ml_model.transcribe.assert_called_once()


def test_send_message_mqtt_utility(mock_mqtt_client):
    """Проверка правильности формирования топика и отправки."""
    send_message_mqtt(mock_mqtt_client, 99, "Включаем двигатель")

    mock_mqtt_client.publish.assert_called_once_with(
        topic="machinist_esp/99", payload="Включаем двигатель", qos=2
    )


def test_send_message_mqtt_exception(mock_mqtt_client):
    """Проверка перехвата ошибок при отправке."""
    mock_mqtt_client.publish.side_effect = Exception("Broker unreachable")

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        send_message_mqtt(mock_mqtt_client, 99, "Текст")

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Wrong data for request"
