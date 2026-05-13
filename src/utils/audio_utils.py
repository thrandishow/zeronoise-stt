import librosa
import io
import os
import tempfile
from fastapi import HTTPException
import soundfile as sf


def convert_audio_to_wav(audio_bytes: bytes) -> bytes:
    """
    Конвертирует аудиоданные в стандартный WAV-формат для обработки.

    Функция выполняет следующие преобразования:
    1. Сохраняет входные байты во временный файл
    2. Загружает аудио с нормализацией параметров:
        - Частота дискретизации: 16kHz
        - Количество каналов: моно (1 канал)
    3. Конвертирует в 16-битный PCM WAV-формат
    4. Удаляет временный файл после обработки

    Args:
        audio_bytes (bytes): Исходные аудиоданные в любом поддерживаемом формате
            (MP3, WAV, FLAC, OGG и др.)

    Returns:
        bytes: Аудиоданные в формате WAV с параметрами:
            - Частота дискретизации: 16000 Гц
            - Битовая глубина: 16 бит
            - Каналы: моно (1)

    Raises:
        HTTPException (400): При ошибках конвертации:
            - Неподдерживаемый аудиоформат
            - Поврежденные аудиоданные
            - Проблемы с файловой системой
            - Отсутствие необходимых кодеков
    """
    temp_input_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".tmp", delete=False) as temp_input:
            temp_input.write(audio_bytes)
            temp_input_path = temp_input.name

        audio, _ = librosa.load(temp_input_path, sr=16000, mono=True)

        buffer = io.BytesIO()
        sf.write(buffer, audio, 16000, format="WAV", subtype="PCM_16")
        buffer.seek(0)
        return buffer.getvalue()

    except Exception as e:
        error_detail = f"Audio conversion error: {str(e)}"
        raise HTTPException(status_code=400, detail=error_detail) from e

    finally:
        if temp_input_path and os.path.exists(temp_input_path):
            try:
                os.unlink(temp_input_path)
            except OSError:
                pass


def transcribe_audio(audio_bytes: bytes, model) -> str:
    """
    Выполняет транскрибацию аудио в текст с использованием pretrained модели.
    """
    try:
        wav_bytes = convert_audio_to_wav(audio_bytes)
        audio, _ = librosa.load(io.BytesIO(wav_bytes), sr=16000)

        transcription = model.transcribe(audio)
        print(transcription["text"])
        return transcription["text"]

    except HTTPException:
        raise

    except Exception as e:
        error_detail = f"Internal transcription error: {str(e)}"
        raise HTTPException(status_code=500, detail=error_detail) from e
