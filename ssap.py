import asyncio
import json
import ssl
import logging
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass, field
import websockets

logger = logging.getLogger("ssap")

HANDSHAKE_PAYLOAD = {
    "forcePairing": False,
    "pairingType": "PROMPT",
    "manifest": {
        "manifestVersion": 1,
        "appVersion": "1.0",
        "signed": {
            "created": "20240101",
            "appId": "com.multiview.controller",
            "vendorId": "com.multiview",
            "localizedAppNames": {"": "MultiView Controller"},
            "localizedVendorNames": {"": "MultiView"},
            "permissions": [
                "LAUNCH", "LAUNCH_WEBAPP", "APP_TO_APP",
                "CONTROL_AUDIO", "CONTROL_DISPLAY",
                "CONTROL_INPUT_JOYSTICK", "CONTROL_INPUT_MEDIA_RECORDING",
                "CONTROL_INPUT_MEDIA_PLAYBACK", "CONTROL_INPUT_TV",
                "CONTROL_POWER", "CONTROL_INPUT_TEXT",
                "READ_APP_STATUS", "READ_CURRENT_CHANNEL",
                "READ_INPUT_DEVICE_LIST", "READ_NETWORK_STATE",
                "READ_RUNNING_APPS", "READ_TV_CHANNEL_LIST",
                "READ_INSTALLED_APPS", "WRITE_NOTIFICATION",
                "READ_TV_CURRENT_TIME", "READ_TV_DEVICE_INFO",
                "READ_POWER_STATE", "READ_COUNTRY_INFO",
                "READ_SETTINGS", "CONTROL_TV_SCREEN",
                "CONTROL_TV_STANBY", "CONTROL_FAVORITE_GROUP",
                "CONTROL_USER_INFO", "CHECK_BLUETOOTH_DEVICE",
                "CONTROL_BLUETOOTH", "CONTROL_TIMER_INFO",
                "STB_INTERNAL_CONNECTION", "CONTROL_RECORDING",
                "READ_RECORDING_STATE", "WRITE_RECORDING_LIST",
                "READ_RECORDING_LIST", "READ_RECORDING_SCHEDULE",
                "WRITE_RECORDING_SCHEDULE", "READ_STORAGE_DEVICE_LIST",
                "READ_TV_PROGRAM_INFO", "CONTROL_BOX_CHANNEL",
                "READ_TV_ACR", "READ_TV_CONTENT_STATE",
                "READ_TV_CURRENT_TIME", "ADD_LAUNCHER_CHANNEL",
                "SET_CHANNEL_SKIP", "RELEASE_CHANNEL_SKIP",
                "CONTROL_CHANNEL_BLOCK", "DELETE_SELECT_CHANNEL",
                "CONTROL_CHANNEL_GROUP", "SCAN_TV_CHANNELS",
                "CONTROL_TV_POWER", "CONTROL_WOL"
            ],
            "serial": "multiview-001"
        },
        "permissions": [
            "LAUNCH", "LAUNCH_WEBAPP", "APP_TO_APP",
            "CONTROL_AUDIO", "CONTROL_DISPLAY",
            "CONTROL_INPUT_JOYSTICK", "CONTROL_INPUT_MEDIA_RECORDING",
            "CONTROL_INPUT_MEDIA_PLAYBACK", "CONTROL_INPUT_TV",
            "CONTROL_POWER", "CONTROL_INPUT_TEXT",
            "READ_APP_STATUS", "READ_CURRENT_CHANNEL",
            "READ_INPUT_DEVICE_LIST", "READ_NETWORK_STATE",
            "READ_RUNNING_APPS", "READ_TV_CHANNEL_LIST",
            "READ_INSTALLED_APPS", "WRITE_NOTIFICATION",
            "READ_TV_CURRENT_TIME", "READ_TV_DEVICE_INFO",
            "READ_POWER_STATE", "READ_COUNTRY_INFO",
            "READ_SETTINGS", "CONTROL_TV_SCREEN",
            "CONTROL_TV_STANBY", "CONTROL_FAVORITE_GROUP",
            "CONTROL_USER_INFO", "CHECK_BLUETOOTH_DEVICE",
            "CONTROL_BLUETOOTH", "CONTROL_TIMER_INFO",
            "STB_INTERNAL_CONNECTION", "CONTROL_RECORDING",
            "READ_RECORDING_STATE", "WRITE_RECORDING_LIST",
            "READ_RECORDING_LIST", "READ_RECORDING_SCHEDULE",
            "WRITE_RECORDING_SCHEDULE", "READ_STORAGE_DEVICE_LIST",
            "READ_TV_PROGRAM_INFO", "CONTROL_BOX_CHANNEL",
            "READ_TV_ACR", "READ_TV_CONTENT_STATE",
            "READ_TV_CURRENT_TIME", "ADD_LAUNCHER_CHANNEL",
            "SET_CHANNEL_SKIP", "RELEASE_CHANNEL_SKIP",
            "CONTROL_CHANNEL_BLOCK", "DELETE_SELECT_CHANNEL",
            "CONTROL_CHANNEL_GROUP", "SCAN_TV_CHANNELS",
            "CONTROL_TV_POWER", "CONTROL_WOL"
        ],
        "signatures": [{"signatureVersion": 1, "signature": ""}]
    }
}

KNOWN_URIS = {
    "get_inputs": "ssap://tv/getExternalInputList",
    "switch_input": "ssap://tv/switchInput",
    "get_volume": "ssap://audio/getVolume",
    "set_volume": "ssap://audio/setVolume",
    "get_apps": "ssap://com.webos.applicationManager/listApps",
    "launch_app": "ssap://com.webos.applicationManager/launch",
    "get_foreground": "ssap://com.webos.applicationManager/getForegroundAppInfo",
    "get_services": "ssap://api/getServiceList",
    "get_system_info": "ssap://system/getSystemInfo",
    "get_sw_info": "ssap://com.webos.service.update/getCurrentSWInformation",
    "get_device_info": "ssap://com.webos.service.tv.device/getDeviceInfo",
    "get_tv_info": "ssap://tv/getChannelProgramInfo",
    "get_settings": "ssap://settings/getSystemSettings",
    "power_off": "ssap://system/turnOff",
    "power_state": "ssap://com.webos.service.tvpower/power/getPowerState",
    "screen_on": "ssap://com.webos.service.tvpower/power/turnOnScreen",
    "screen_off": "ssap://com.webos.service.tvpower/power/turnOffScreen",
    "toast": "ssap://system.notifications/createToast",
}

MULTIVIEW_PROBE_URIS = [
    "ssap://com.webos.service.multiview/getStatus",
    "ssap://com.webos.service.multiview/getMultiViewStatus",
    "ssap://com.webos.service.multiview/setMultiView",
    "ssap://com.webos.service.tv.display/getMultiView",
    "ssap://com.webos.service.tv.display/setMultiView",
    "ssap://com.webos.service.tv.display/getDisplayStatus",
    "ssap://com.webos.service.pip/getStatus",
    "ssap://com.webos.service.pip/getPIPStatus",
    "ssap://tv/getMultiViewStatus",
    "ssap://tv/setMultiView",
    "ssap://tv/getPIPStatus",
    "ssap://tv/setPIP",
    "ssap://com.webos.service.config/getConfigs",
    "ssap://settings/getSystemSettings",
]

KEY_FILE = Path(__file__).parent / ".tv_client_key"


@dataclass
class ErrorLog:
    uri: str
    payload: dict
    response: dict
    error_type: str
    timestamp: str = ""

    def to_dict(self):
        return {
            "uri": self.uri,
            "payload": self.payload,
            "response": self.response,
            "error_type": self.error_type,
            "timestamp": self.timestamp,
        }


class SSAPClient:
    def __init__(self, host: str, port: int = 3001, secure: bool = True):
        self.host = host
        self.port = port
        self.secure = secure
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.client_key: Optional[str] = None
        self._msg_id = 0
        self._pending: dict[str, asyncio.Future] = {}
        self._subscriptions: dict[str, Callable] = {}
        self._recv_task: Optional[asyncio.Task] = None
        self.error_log: list[ErrorLog] = []
        self.on_status_change: Optional[Callable] = None
        self._load_key()

    def _load_key(self):
        if KEY_FILE.exists():
            self.client_key = KEY_FILE.read_text().strip()
            logger.info("Loaded saved client key")

    def _save_key(self, key: str):
        self.client_key = key
        KEY_FILE.write_text(key)
        logger.info("Saved client key")

    @property
    def url(self):
        scheme = "wss" if self.secure else "ws"
        return f"{scheme}://{self.host}:{self.port}"

    @property
    def connected(self):
        return self.ws is not None and self.ws.open

    async def connect(self):
        ssl_ctx = None
        if self.secure:
            ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE

        logger.info(f"Connecting to {self.url}")
        try:
            self.ws = await websockets.connect(
                self.url,
                ssl=ssl_ctx,
                ping_interval=None,
                close_timeout=5,
            )
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self._log_error("connect", {}, {"error": str(e)}, type(e).__name__)
            raise

        self._recv_task = asyncio.create_task(self._recv_loop())
        await self._register()
        if self.on_status_change:
            self.on_status_change(True)

    async def disconnect(self):
        if self._recv_task:
            self._recv_task.cancel()
        if self.ws:
            await self.ws.close()
            self.ws = None
        if self.on_status_change:
            self.on_status_change(False)

    async def _register(self):
        payload = dict(HANDSHAKE_PAYLOAD)
        if self.client_key:
            payload["client-key"] = self.client_key

        resp = await self.request("register", "ssap://pairing/register", payload)
        if resp.get("type") == "registered":
            key = resp.get("payload", {}).get("client-key")
            if key:
                self._save_key(key)
            logger.info("Registered successfully")
        elif resp.get("type") == "response" and "client-key" in resp.get("payload", {}):
            self._save_key(resp["payload"]["client-key"])
            logger.info("Registered (response type)")
        else:
            logger.warning(f"Registration response: {resp}")

    async def _recv_loop(self):
        try:
            async for msg in self.ws:
                data = json.loads(msg)
                msg_id = data.get("id")
                if msg_id and msg_id in self._pending:
                    self._pending[msg_id].set_result(data)
                elif msg_id and msg_id in self._subscriptions:
                    self._subscriptions[msg_id](data)
                else:
                    logger.debug(f"Unhandled message: {data}")
        except websockets.exceptions.ConnectionClosed:
            logger.info("Connection closed")
            if self.on_status_change:
                self.on_status_change(False)
        except asyncio.CancelledError:
            pass

    def _next_id(self):
        self._msg_id += 1
        return f"msg_{self._msg_id}"

    async def request(self, msg_type: str, uri: str, payload: dict = None,
                      timeout: float = 10.0) -> dict:
        msg_id = self._next_id()
        msg = {"type": msg_type, "id": msg_id, "uri": uri}
        if payload:
            msg["payload"] = payload

        future = asyncio.get_event_loop().create_future()
        self._pending[msg_id] = future

        try:
            await self.ws.send(json.dumps(msg))
            result = await asyncio.wait_for(future, timeout)
            return result
        except asyncio.TimeoutError:
            self._log_error(uri, payload or {}, {"error": "timeout"}, "TimeoutError")
            return {"type": "error", "error": "timeout", "payload": {}}
        except Exception as e:
            self._log_error(uri, payload or {}, {"error": str(e)}, type(e).__name__)
            return {"type": "error", "error": str(e), "payload": {}}
        finally:
            self._pending.pop(msg_id, None)

    async def send(self, uri: str, payload: dict = None) -> dict:
        return await self.request("request", uri, payload)

    async def subscribe(self, uri: str, callback: Callable, payload: dict = None):
        msg_id = self._next_id()
        msg = {"type": "subscribe", "id": msg_id, "uri": uri}
        if payload:
            msg["payload"] = payload
        self._subscriptions[msg_id] = callback
        await self.ws.send(json.dumps(msg))
        return msg_id

    def _log_error(self, uri, payload, response, error_type):
        from datetime import datetime
        entry = ErrorLog(
            uri=uri,
            payload=payload,
            response=response,
            error_type=error_type,
            timestamp=datetime.now().isoformat(),
        )
        self.error_log.append(entry)
        logger.error(f"[{error_type}] {uri}: {response}")

    async def get_inputs(self) -> list[dict]:
        resp = await self.send(KNOWN_URIS["get_inputs"])
        devices = resp.get("payload", {}).get("devices", [])
        return devices

    async def switch_input(self, input_id: str) -> dict:
        return await self.send(KNOWN_URIS["switch_input"], {"inputId": input_id})

    async def get_services(self) -> list[dict]:
        resp = await self.send(KNOWN_URIS["get_services"])
        return resp.get("payload", {}).get("services", [])

    async def get_system_info(self) -> dict:
        resp = await self.send(KNOWN_URIS["get_system_info"])
        return resp.get("payload", {})

    async def get_device_info(self) -> dict:
        resp = await self.send(KNOWN_URIS["get_device_info"])
        return resp.get("payload", {})

    async def probe_multiview(self) -> dict:
        results = {}
        for uri in MULTIVIEW_PROBE_URIS:
            resp = await self.send(uri)
            resp_type = resp.get("type", "unknown")
            error = resp.get("payload", {}).get("errorText", resp.get("error", ""))
            results[uri] = {
                "type": resp_type,
                "payload": resp.get("payload", {}),
                "error": error,
                "success": resp_type == "response" and not error,
            }
            logger.info(f"Probe {uri}: type={resp_type} error={error}")
        return results

    async def try_multiview(self, mode: str, inputs: list[str] = None,
                             layout: str = None) -> dict:
        payloads_to_try = []

        if mode == "enable":
            payloads_to_try = [
                {"mode": "on"},
                {"multiView": True},
                {"enable": True},
                {"mode": "multiView"},
                {"action": "enable"},
            ]
        elif mode == "disable":
            payloads_to_try = [
                {"mode": "off"},
                {"multiView": False},
                {"enable": False},
                {"action": "disable"},
            ]
        elif mode == "set_layout":
            base = {}
            if inputs:
                base["inputList"] = inputs
                base["inputs"] = inputs
            if layout:
                base["layout"] = layout
                base["type"] = layout
            payloads_to_try = [base]

        uris_to_try = [
            "ssap://com.webos.service.multiview/setMultiView",
            "ssap://com.webos.service.tv.display/setMultiView",
            "ssap://tv/setMultiView",
        ]

        results = {}
        for uri in uris_to_try:
            for payload in payloads_to_try:
                resp = await self.send(uri, payload)
                key = f"{uri} | {json.dumps(payload)}"
                resp_type = resp.get("type", "unknown")
                error = resp.get("payload", {}).get("errorText", resp.get("error", ""))
                results[key] = {
                    "type": resp_type,
                    "payload": resp.get("payload", {}),
                    "error": error,
                    "success": resp_type == "response" and not error,
                }
                if results[key]["success"]:
                    return results
        return results

    async def send_raw(self, uri: str, payload: dict = None) -> dict:
        return await self.send(uri, payload)

    def export_error_log(self) -> str:
        return json.dumps([e.to_dict() for e in self.error_log], indent=2)
