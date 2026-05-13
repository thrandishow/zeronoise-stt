from paho.mqtt import client as mqtt
from src.config import settings, logger
from fastapi import HTTPException


def on_connect(client: mqtt.Client, userdata, flags, reason_code, properties) -> None:
    """
    Callback-функция, вызываемая при подключении клиента к MQTT-брокеру.

    Эта функция автоматически вызывается Paho-клиентом после завершения подключения.
    Записывает в лог результат подключения, включая версию протокола и детали соединения.

    Args:
        client: Экземпляр Paho MQTT-клиента
        userdata: Пользовательские данные (в данной реализации не используются)
        flags: Словарь с флагами ответа от брокера
        reason_code: Код результата подключения (0=успех, ненулевое=ошибка)
        properties: Объект свойств MQTT v5 с деталями подключения
    """
    protocol_version = "MQTTv5" if properties is not None else "MQTTv3.1.1"
    logger.info(f"Connected to MQTT Broker at {broker_url}:{broker_port}")
    logger.info(f"Connection Result: {reason_code} | Protocol: {protocol_version}")


def on_disconnect(client: mqtt.Client, userdata, rc) -> None:
    """
    Callback-функция, вызываемая при отключении клиента от MQTT-брокера.

    Обрабатывает неожиданные разрывы соединения и записывает причину отключения в лог.
    Paho-клиент автоматически попытается восстановить соединение после этого callback.

    Args:
        client: Экземпляр Paho MQTT-клиента
        userdata: Пользовательские данные (в данной реализации не используются)
        rc: Код причины отключения (0=корректное отключение, ненулевое=аварийное)
    """
    reason = "Clean disconnect" if rc == 0 else f"Unexpected disconnect (RC={rc})"
    logger.error(f"MQTT Connection Lost: {reason}")
    logger.error("Client will automatically attempt reconnection")


mqtt_client = mqtt.Client(
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    protocol=mqtt.MQTTv5,
)

mqtt_client.on_connect = on_connect
mqtt_client.on_disconnect = on_disconnect

try:
    mqtt_client.connect(settings.broker_url, settings.broker_port, keepalive=60)
except ConnectionRefusedError:
    logger.critical(
        f"Connection refused by broker at {settings.broker_url}:{settings.broker_port}"
    )
except OSError as e:
    logger.critical(f"Network error connecting to broker: {str(e)}")
else:
    mqtt_client.loop_start()


def send_message_mqtt(mqtt_client: mqtt.Client, id: int, message: str):
    """
    Отправляет сообщение в MQTT-топик для конкретного устройства.

    Эндпоинт принимает идентификатор устройства и текстовое сообщение через URL-параметры,
    публикует их в MQTT-брокер с гарантией доставки (QoS=2).
    """
    try:
        mqtt_client.publish(topic=f"machinist_esp/{id}", payload=message, qos=2)
    except:
        raise HTTPException(status_code=400, detail="Wrong data for request")
