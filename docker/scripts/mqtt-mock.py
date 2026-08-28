#!/usr/bin/env python3
"""Publish retained demo MQTT topics for the HomeUI docker stand."""

import time

import paho.mqtt.client as mqtt

BROKER = "127.0.0.1"
PORT = 1883

TOPICS = {
    "/devices/mock-lamp/meta/name": "Demo Lamp",
    "/devices/mock-lamp/controls/brightness/meta/type": "range",
    "/devices/mock-lamp/controls/brightness/meta/min": "0",
    "/devices/mock-lamp/controls/brightness/meta/max": "100",
    "/devices/mock-lamp/controls/brightness": "42",
    "/devices/mock-lamp/controls/power/meta/type": "switch",
    "/devices/mock-lamp/controls/power": "0",
}


def publish_all(client: mqtt.Client) -> None:
    for topic, payload in TOPICS.items():
        client.publish(topic, payload, qos=0, retain=True)
        print(f"published {topic} = {payload!r}", flush=True)


def main() -> None:
    while True:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        try:
            client.connect(BROKER, PORT, keepalive=60)
            publish_all(client)
            client.loop_forever()
        except Exception as exc:  # pylint: disable=broad-exception-caught
            print(f"mqtt-mock error: {exc}", flush=True)
            time.sleep(5)
        finally:
            try:
                client.disconnect()
            except Exception:  # pylint: disable=broad-exception-caught
                pass


if __name__ == "__main__":
    main()
