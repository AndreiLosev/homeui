#!/usr/bin/env python3
"""Mock wb-mqtt-db history RPC for the HomeUI docker stand."""

import json
import math
import sqlite3
import time
from pathlib import Path

import paho.mqtt.client as mqtt

BROKER = "127.0.0.1"
PORT = 1883
DB_PATH = Path("/var/lib/wirenboard/db/data.db")
RPC_TOPIC = "/rpc/v1/db_logger/history/get_values/+"
DEVICE_TOPIC = "/devices/+/controls/+"

def connect_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device TEXT NOT NULL,
            control TEXT NOT NULL,
            UNIQUE(device, control)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS history_values (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id INTEGER NOT NULL,
            value TEXT NOT NULL,
            ts REAL NOT NULL,
            retain INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(channel_id) REFERENCES channels(id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_values_channel_ts ON history_values(channel_id, ts)"
    )
    conn.commit()
    return conn


def get_or_create_channel(conn: sqlite3.Connection, device: str, control: str) -> int:
    row = conn.execute(
        "SELECT id FROM channels WHERE device = ? AND control = ?",
        (device, control),
    ).fetchone()
    if row:
        return int(row["id"])
    cursor = conn.execute(
        "INSERT INTO channels(device, control) VALUES (?, ?)",
        (device, control),
    )
    conn.commit()
    return int(cursor.lastrowid)


def insert_value(
    conn: sqlite3.Connection,
    device: str,
    control: str,
    value: str,
    ts: float,
    retain: bool,
) -> None:
    channel_id = get_or_create_channel(conn, device, control)
    conn.execute(
        "INSERT INTO history_values(channel_id, value, ts, retain) VALUES (?, ?, ?, ?)",
        (channel_id, value, ts, 1 if retain else 0),
    )
    conn.commit()


def seed_demo_data(conn: sqlite3.Connection) -> None:
    count = conn.execute("SELECT COUNT(*) AS cnt FROM history_values").fetchone()["cnt"]
    if count:
        return

    now = time.time()
    start = now - 24 * 60 * 60
    step = 5 * 60

    print("history-mock: seeding demo history", flush=True)
    ts = start
    index = 0
    while ts <= now:
        brightness = int(50 + 40 * math.sin(index / 12))
        power = "1" if (index // 24) % 2 == 0 else "0"
        insert_value(conn, "mock-lamp", "brightness", str(brightness), ts, False)
        insert_value(conn, "mock-lamp", "power", power, ts, False)
        ts += step
        index += 1


def parse_device_topic(topic: str) -> tuple[str, str] | None:
    parts = topic.split("/")
    if len(parts) != 5 or parts[0] != "" or parts[1] != "devices" or parts[3] != "controls":
        return None
    if parts[4] == "meta" or "meta" in parts[4:]:
        return None
    return parts[2], parts[4]


def query_values(conn: sqlite3.Connection, params: dict) -> list[dict]:
    channels = params.get("channels") or []
    if not channels:
        return []

    timestamp = params.get("timestamp") or {}
    gt = timestamp.get("gt")
    lt = timestamp.get("lt")
    limit = int(params.get("max_records") or params.get("limit") or 1000)
    min_interval = params.get("min_interval")

    results: list[dict] = []
    for device, control in channels:
        channel_id = get_or_create_channel(conn, device, control)
        query = """
            SELECT v.id, v.value, v.ts, v.retain, c.id AS channel_id
            FROM history_values v
            JOIN channels c ON c.id = v.channel_id
            WHERE c.id = ?
        """
        args: list[object] = [channel_id]
        if gt is not None:
            query += " AND v.ts > ?"
            args.append(float(gt))
        if lt is not None:
            query += " AND v.ts < ?"
            args.append(float(lt))
        query += " ORDER BY v.ts ASC LIMIT ?"
        args.append(limit)

        rows = conn.execute(query, args).fetchall()
        if min_interval and rows:
            rows = thin_rows(rows, int(min_interval))

        for row in rows:
            value = row["value"]
            results.append({
                "c": int(row["channel_id"]),
                "i": int(row["id"]),
                "v": value,
                "t": float(row["ts"]),
                "min": value,
                "max": value,
                "retain": bool(row["retain"]),
            })

    results.sort(key=lambda item: item["t"])
    if len(results) > limit:
        results = results[:limit]
    return results


def thin_rows(rows: list[sqlite3.Row], min_interval: int) -> list[sqlite3.Row]:
    if min_interval <= 0 or not rows:
        return list(rows)

    kept: list[sqlite3.Row] = []
    last_ts = None
    for row in rows:
        ts = float(row["ts"])
        if last_ts is None or ts - last_ts >= min_interval:
            kept.append(row)
            last_ts = ts
    if rows and kept and kept[-1]["id"] != rows[-1]["id"]:
        kept.append(rows[-1])
    return kept


class HistoryMock:
    def __init__(self) -> None:
        self.conn = connect_db()
        seed_demo_data(self.conn)
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def _on_connect(
        self,
        client: mqtt.Client,
        _userdata: object,
        _flags: object,
        reason_code: mqtt.ReasonCode,
        _properties: object = None,
    ) -> None:
        if reason_code != 0:
            print(f"history-mock: connect failed ({reason_code})", flush=True)
            return
        client.subscribe(DEVICE_TOPIC)
        client.subscribe(RPC_TOPIC)
        print("history-mock: connected", flush=True)

    def _on_message(self, _client: mqtt.Client, _userdata: object, msg: mqtt.MQTTMessage) -> None:
        topic = msg.topic
        if topic.startswith("/rpc/v1/db_logger/history/get_values/"):
            self._handle_rpc(topic, msg.payload)
            return

        parsed = parse_device_topic(topic)
        if not parsed:
            return

        device, control = parsed
        payload = msg.payload.decode("utf-8", errors="replace")
        insert_value(self.conn, device, control, payload, time.time(), msg.retain)

    def _handle_rpc(self, topic: str, payload: bytes) -> None:
        try:
            request = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            print(f"history-mock: bad RPC payload: {exc}", flush=True)
            return

        request_id = request.get("id")
        if request_id is None:
            return

        params = request.get("params") or {}
        values = query_values(self.conn, params)
        reply = json.dumps({"id": request_id, "result": {"values": values}})
        self.client.publish(f"{topic}/reply", reply, qos=0)

    def run(self) -> None:
        while True:
            try:
                self.client.connect(BROKER, PORT, keepalive=60)
                self.client.loop_forever()
            except Exception as exc:  # pylint: disable=broad-exception-caught
                print(f"history-mock error: {exc}", flush=True)
                time.sleep(5)
            finally:
                try:
                    self.client.disconnect()
                except Exception:  # pylint: disable=broad-exception-caught
                    pass


def main() -> None:
    HistoryMock().run()


if __name__ == "__main__":
    main()
