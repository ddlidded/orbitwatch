import json
import logging
from collections import defaultdict
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class Connection:
    def __init__(self, websocket: WebSocket, user_id: str, roles: set[str], instruments: set[str]):
        self.websocket = websocket
        self.user_id = user_id
        self.roles = roles
        self.instruments = instruments
        self.subscriptions: set[str] = set()


class RealtimeManager:
    def __init__(self) -> None:
        self.connections: dict[int, Connection] = {}
        self.channels: dict[str, set[int]] = defaultdict(set)
        self._counter = 0

    async def connect(self, websocket: WebSocket, user_id: str, roles: set[str], instruments: set[str]) -> int:
        await websocket.accept()
        self._counter += 1
        conn_id = self._counter
        self.connections[conn_id] = Connection(websocket, user_id, roles, instruments)
        logger.info('websocket connected user=%s conn=%s', user_id, conn_id)
        return conn_id

    def disconnect(self, conn_id: int) -> None:
        conn = self.connections.pop(conn_id, None)
        if conn:
            for channel in list(conn.subscriptions):
                self.channels[channel].discard(conn_id)
            logger.info('websocket disconnected conn=%s', conn_id)

    def subscribe(self, conn_id: int, channel: str) -> bool:
        conn = self.connections.get(conn_id)
        if not conn:
            return False
        if not self._authorize_channel(conn, channel):
            return False
        conn.subscriptions.add(channel)
        self.channels[channel].add(conn_id)
        return True

    def _authorize_channel(self, conn: Connection, channel: str) -> bool:
        if ':' not in channel:
            return False
        scope, resource_id = channel.split(':', 1)
        if scope in ('instrument', 'sequence', 'sample', 'alerts'):
            return resource_id in conn.instruments or 'system_admin' in conn.roles
        return False

    async def broadcast(self, channel: str, payload: dict[str, Any]) -> None:
        message = json.dumps({'channel': channel, 'payload': payload})
        dead: list[int] = []
        for conn_id in list(self.channels.get(channel, [])):
            conn = self.connections.get(conn_id)
            if not conn:
                dead.append(conn_id)
                continue
            try:
                await conn.websocket.send_text(message)
            except Exception as exc:
                logger.warning('websocket send failed conn=%s: %s', conn_id, exc)
                dead.append(conn_id)
        for conn_id in dead:
            self.disconnect(conn_id)

    async def send(self, conn_id: int, payload: dict[str, Any]) -> None:
        conn = self.connections.get(conn_id)
        if conn:
            await conn.websocket.send_text(json.dumps(payload))


manager = RealtimeManager()
