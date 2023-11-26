import asyncio
import builtins
from dataclasses import dataclass
from enum import IntEnum


class PacketType(IntEnum):
    LOGIN = 3
    EXECUTE = 2
    RESPONSE = 0


@dataclass
class Packet:
    """Packet structure"""

    request_id: int
    """Request ID"""

    type: PacketType | int
    """Packet type"""

    data: str | bytes
    """Packet data"""

    def must_bytes(self) -> bytes:
        if not isinstance(self.data, bytes):
            raise ValueError("Data is not bytes")
        return self.data

    def must_str(self) -> str:
        if not isinstance(self.data, str):
            raise ValueError("Data is not str")
        return self.data


def _build_packet(packet: Packet) -> bytes:
    """Builds an RCON packet.

    Parameters
    ----------
    request_id: :class:`int`
        Request ID
    type: :class:`int`
        Packet type
    data: :class:`str` | :class:`bytes`
        Packet data

    Returns
    -------
    :class:`bytes`
    .. list-table:: Packet format
       :widths: 25 25 50
       :header-rows: 1

       * - field name
         - field type
         - description
       * - request_id
         - int32
         - request id
       * - type
         - int32
         - packet type, 3 for login, 2 to run a command, 0 for a multi-packet response
       * - payload
         - byte[]
         - packet data, e.g. password, command, etc.
       * - _padding
         - byte
         - always zero
    """
    if isinstance(packet.data, str):
        d = packet.data.encode()
    elif isinstance(packet.data, bytes):
        d = packet.data
    else:
        raise TypeError(f"expected str or bytes, got {type(packet.data)!r}")
    if len(d) > 4096:
        raise ValueError(f"too large data: {len(d)} > 4096")
    return (
        packet.request_id.to_bytes(4, "little", signed=True)
        + (packet.type if isinstance(packet.type, int) else packet.type.value).to_bytes(
            4, "little", signed=True
        )
        + d
        + b"\0"
    )


class RCONClient:
    """The RCON client."""

    _i: int

    host: str
    """RCON host."""

    port: int
    """RCON port."""

    _reader: asyncio.StreamReader
    _writer: asyncio.StreamWriter

    def __init__(self, host: str = "127.0.0.1", port: int = 25575) -> None:
        """Initialize RCON client."""
        self._i = 0
        self.host = host
        self.port = port

    async def open(self) -> None:
        self._reader, self._writer = await asyncio.open_connection(self.host, self.port)

    async def close(self) -> None:
        """Closes a RCON connection."""

        self._writer.close()

    async def _recv_packet(self) -> Packet:
        nb = await self._reader.read(4)
        if len(nb) != 4:
            raise ValueError(
                f"incorrect packet: got {len(nb)} bytes, expected 4 as length"
            )
        n = int.from_bytes(nb, "little", signed=False)
        if n < 9:
            raise ValueError(f"too small packet: expected at least 9 bytes, got {n}")
        if n > 1455:
            raise ValueError(
                f"too big packet: expected not more than 1455 bytes, got {n}"
            )
        packet = await self._reader.read(n)
        if len(packet) != n:
            raise ValueError(
                f"incorrect packet: first part specified {n}, but recieved second part was {len(packet)} bytes long"
            )
        return Packet(
            int.from_bytes(packet[0:4], "little", signed=True),
            int.from_bytes(packet[4:8], "little", signed=True),
            packet[8:-1],
        )

    async def _recv_text_packet(self) -> Packet:
        packet = await self._recv_packet()
        d = packet.must_bytes()
        zero = d.find(b"\0")
        if zero == -1:
            raise ValueError("data is not zero-terminated")
        return Packet(packet.request_id, packet.type, d[:zero])

    async def _send_packet(self, packet: Packet) -> None:
        payload = _build_packet(packet)
        self._writer.write(len(payload).to_bytes(4, "little", signed=False) + payload)
        await self._writer.drain()

    async def _send_text_packet(self, packet: Packet) -> None:
        return await self._send_packet(
            Packet(
                packet.request_id,
                packet.type,
                packet.must_str().encode("utf_8") + b"\0",
            )
        )

    async def login(self, password: str) -> None:
        """Logins using password"""

        i = self._i
        self._i += 1

        await self._send_text_packet(Packet(i, PacketType.LOGIN, password))
        packet = await self._recv_packet()
        if packet.request_id != i:
            raise ValueError(
                f"Invalid request ID (expected {i}, got {packet.request_id})"
            )

    async def execute(self, command: str) -> bytes:
        """Executes a command and returns its response"""

        i = self._i
        self._i += 1

        await self._send_text_packet(Packet(i, PacketType.EXECUTE, command))
        result: bytes = b""
        while True:
            packet = await self._recv_text_packet()
            if packet.request_id != i:
                raise ValueError(
                    f"Invalid request ID (expected {i}, got {packet.request_id})"
                )
            if packet.type != PacketType.RESPONSE.value:
                raise ValueError(
                    f"Invalid response type (expected {PacketType.RESPONSE.value}, got {packet.type})"
                )
            payload = packet.must_bytes()
            print(payload)
            result += payload
            if len(payload) < 4096:
                break
        return result
