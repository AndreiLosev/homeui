#!/usr/bin/env python3
"""Publish retained demo MQTT topics for the HomeUI docker stand."""

import math
import threading
import time

import paho.mqtt.client as mqtt

BROKER = "127.0.0.1"
PORT = 1883
UPDATE_INTERVAL_S = 15

RETAINED_TOPICS = {
    "/devices/mock-lamp/meta/name": "Demo Lamp",
    "/devices/mock-lamp/controls/brightness/meta/type": "range",
    "/devices/mock-lamp/controls/brightness/meta/min": "0",
    "/devices/mock-lamp/controls/brightness/meta/max": "100",
    "/devices/mock-lamp/controls/brightness": "42",
    "/devices/mock-lamp/controls/power/meta/type": "switch",
    "/devices/mock-lamp/controls/power": "0",
}


def publish_retained(client: mqtt.Client) -> None:
    for topic, payload in RETAINED_TOPICS.items():
        client.publish(topic, payload, qos=0, retain=True)
        print(f"published {topic} = {payload!r}", flush=True)


def publish_live_values(client: mqtt.Client, tick: int) -> None:
    brightness = int(50 + 40 * math.sin(tick / 6))
    power = "1" if (tick // 4) % 2 == 0 else "0"
    client.publish("/devices/mock-lamp/controls/brightness", str(brightness), qos=0, retain=False)
    client.publish("/devices/mock-lamp/controls/power", power, qos=0, retain=False)
    print(
        f"published live brightness={brightness}, power={power}",
        flush=True,
    )


def value_loop(client: mqtt.Client, stop_event: threading.Event) -> None:
    tick = 0
    while not stop_event.wait(UPDATE_INTERVAL_S):
        publish_live_values(client, tick)
        tick += 1


def main() -> None:
    while True:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        stop_event = threading.Event()
        worker = None
        try:
            client.connect(BROKER, PORT, keepalive=60)
            publish_retained(client)
            worker = threading.Thread(target=value_loop, args=(client, stop_event), daemon=True)
            worker.start()
            client.loop_forever()
        except Exception as exc:  # pylint: disable=broad-exception-caught
            print(f"mqtt-mock error: {exc}", flush=True)
            time.sleep(5)
        finally:
            stop_event.set()
            if worker is not None:
                worker.join(timeout=1)
            try:
                client.disconnect()
            except Exception:  # pylint: disable=broad-exception-caught
                pass


if __name__ == "__main__":
    main()
