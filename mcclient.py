# -*- coding: utf-8 -*-
"""Synthetic MC 1.21.9/26.1 (protocol 775) client for AzureProxy E2E:
handshake -> login (offline) -> config phase -> play -> /say command -> verify SystemChat echo."""
import socket
import struct
import json
import zlib
import sys
import time

HOST = sys.argv[1] if len(sys.argv) > 1 else '127.0.0.1'
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 25571
NAME = sys.argv[3] if len(sys.argv) > 3 else 'exp7probe'
CMD = sys.argv[4] if len(sys.argv) > 4 else 'say EXP7-PROXY-E2E'
PROTO = 775


def varint(n):
    out = b''
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out += bytes([b | 0x80])
        else:
            out += bytes([b])
            return out


def cstring(s):
    b = s.encode('utf-8')
    return varint(len(b)) + b


class Conn:
    def __init__(self):
        self.s = socket.create_connection((HOST, PORT), timeout=8)
        self.compression = None
        self.raw = bytearray()

    def send_frame(self, packet_id, payload):
        if self.compression is None:
            body = varint(packet_id) + payload
            self.s.sendall(varint(len(body)) + body)
        else:
            inner = varint(packet_id) + payload
            if len(inner) >= self.compression:
                data = zlib.compress(inner)
                body = varint(len(data)) + data  # data-len varint INSIDE frame
                self.s.sendall(varint(len(body)) + body)
            else:
                body = varint(0) + inner
                self.s.sendall(varint(len(body)) + body)

    def read_exact(self, n):
        out = b''
        while len(out) < n:
            chunk = self.s.recv(n - len(out))
            if not chunk:
                raise ConnectionError('eof mid-read')
            out += chunk
        return out

    def read_byte(self):
        return self.read_exact(1)[0]

    def read_varint(self):
        num = 0
        shift = 0
        while True:
            v = self.read_byte()
            num |= (v & 0x7F) << shift
            if not (v & 0x80):
                return num
            shift += 7

    def recv_packet(self):
        plen = self.read_varint()
        data = self.read_exact(plen)
        self.raw += data
        if self.compression is not None:
            dlen = 0
            shift = 0
            pos = 0
            while True:
                v = data[pos]
                dlen |= (v & 0x7F) << shift
                pos += 1
                if not (v & 0x80):
                    break
                shift += 7
            if dlen == 0:
                inner = data[pos:]
            else:
                inner = zlib.decompress(data[pos:])
            pid, rest = 0, b''
            shift = 0
            p = 0
            while True:
                v = inner[p]
                pid |= (v & 0x7F) << shift
                p += 1
                if not (v & 0x80):
                    break
                shift += 7
            return pid, inner[p:]
        pid = 0
        shift = 0
        p = 0
        while True:
            v = data[p]
            pid |= (v & 0x7F) << shift
            p += 1
            if not (v & 0x80):
                break
            shift += 7
        return pid, data[p:]

    def close(self):
        try:
            self.s.close()
        except Exception:
            pass


def u32_to_uuid(u):
    return str(uuid.UUID(bytes=struct.pack('>II', u >> 32, u & 0xffffffff)))


import uuid
import random

c = Conn()
facts = {}

# 1) handshake (2=login)
c.send_frame(0x00, varint(PROTO) + cstring('127.0.0.1') + struct.pack('>H', PORT) + varint(2))
# 2) login start (1.20.2+): name(string) + holderUuid(16 bytes, always present)
u = uuid.uuid4()
c.send_frame(0x00, cstring(NAME) + u.bytes)

state = 'LOGIN'
play_seen = False
command_sent = False
echo_found = False
t0 = time.time()
try:
    while time.time() - t0 < 15:
        pid, payload = c.recv_packet()
        if state == 'LOGIN':
            if pid == 0x03:  # SetCompression
                thresh = 0
                shift = 0
                p = 0
                while True:
                    v = payload[p]
                    thresh |= (v & 0x7F) << shift
                    p += 1
                    if not (v & 0x80):
                        break
                    shift += 7
                c.compression = thresh
                print('[LOGIN] compression threshold=%d' % thresh)
            elif pid == 0x02:  # LoginSuccess
                print('[LOGIN] LoginSuccess (len=%d)' % len(payload))
                c.send_frame(0x03, b'')  # LoginAcknowledged
                state = 'CONFIG'
            elif pid == 0x00:  # Disconnect
                print('[LOGIN] DISCONNECTED: %r' % payload)
                sys.exit(2)
        elif state == 'CONFIG':
            print('[CONFIG] pid=0x%02x len=%d' % (pid, len(payload)))
            if pid == 0x03:  # FinishedUpdate (server done config)
                print('[CONFIG] FinishedUpdate received -> ack, entering PLAY')
                c.send_frame(0x03, b'')  # FinishedUpdate ack
                state = 'PLAY'
            elif pid == 0x02:  # Disconnect
                print('[CONFIG] DISCONNECT hex: %s' % payload.hex())
                sys.exit(3)
            elif pid == 0x00:  # CookieRequest: cookie key(string) + bool
                print('[CONFIG] cookie request (ignored)')
            if not facts.get('info_sent') and pid in (0x0C, 0x07, 0x0D, 0x0E, 0x0F, 0x10):
                # ClientInformation (0x00): locale, viewDist byte, chatMode varint, colors bool, skin byte, mainHand varint, filter bool, listing bool, particle varint
                body = cstring('en_us') + bytes([8]) + varint(0) + b'\x00' + bytes([0x7F]) + varint(1) + b'\x00' + b'\x01' + varint(0)
                c.send_frame(0x00, body)
                facts['info_sent'] = True
                print('[CONFIG] sent ClientInformation')
            if not facts.get('packs_sent') and pid == 0x0E:
                # server has sent the known-packs list -> respond with our selection (empty)
                c.send_frame(0x07, varint(0))
                facts['packs_sent'] = True
                print('[CONFIG] sent SelectKnownPacks (empty)')
        else:  # PLAY
            facts.setdefault('seen', {})
            facts['seen'][pid] = facts['seen'].get(pid, 0) + 1
            if not facts.get('tr'):
                print('[PLAY] pid=0x%02x len=%d' % (pid, len(payload)))
            # channel scan: any packet containing the marker bytes
            if facts.get('sent') and b'EXP7-PROXY-E2E' in payload:
                print('[CHANNEL] pid=0x%02x len=%d CONTAINS MARKER' % (pid, len(payload)))
                facts['marker_pid'] = pid
            # 26.1 (1.21.9+): player-loaded + client-tick-end keep the player "in world"
            if not facts.get('loaded'):
                c.send_frame(0x2C, b'')  # ServerboundPlayerLoaded
                facts['loaded'] = True
                print('[PLAY] sent PlayerLoaded')
            now = time.time()
            if now - facts.get('last_tick', 0) > 0.2:
                c.send_frame(0x0D, b'')  # ServerboundClientTickEnd
                facts['last_tick'] = now
            if not facts.get('sent') and facts.get('play'):
                if not command_sent:
                    ts = int(time.time() * 1000)
                    salt = random.getrandbits(64)
                    if salt > 2 ** 63 - 1:
                        salt -= 2 ** 64
                    body = cstring(CMD) + struct.pack('>qq', ts, salt) + varint(0) + varint(0) + b'\x00\x00\x00' + b'\x00'
                    c.send_frame(0x08, body)  # chat_command_signed (id verified by backend decoder)
                    command_sent = True
                    print('[PLAY] sent command: %r' % CMD)
            if pid == 0x2C:  # JoinGame (26.1.2) - marker
                play_seen = True
                facts['play'] = True
                print('[PLAY] JoinGame/marker (len=%d) -> play state' % len(payload))
            elif pid in (0x78, 0x79):  # SystemChat (26.1.2 = 0x78; velocity-era guess 0x79)
                shift = 0
                slen = 0
                p = 0
                while True:
                    v = payload[p]
                    slen |= (v & 0x7F) << shift
                    p += 1
                    if not (v & 0x80):
                        break
                    shift += 7
                js = payload[p:p + slen].decode('utf-8', 'replace')
                try:
                    obj = json.loads(js)
                    txt = obj.get('text', '') + ''.join(x.get('text', '') for x in obj.get('extra', []))
                except Exception:
                    txt = js
                print('[PLAY] SystemChat(0x%02x): %r' % (pid, txt))
                if 'EXP7-PROXY-E2E' in txt:
                    echo_found = True
            elif pid == 0x02:  # config start? (StartUpdate) ignore
                pass
finally:
    c.close()

print('VERDICT: play=%s command=%s echo=%s' % (play_seen, command_sent, echo_found))
if 'seen' in facts:
    print('pid histogram (top 20):')
    for pid, cnt in sorted(facts['seen'].items(), key=lambda kv: -kv[1])[:20]:
        print('  0x%02x x%d' % (pid, cnt))
with open('raw-dump.bin', 'wb') as f:
    f.write(bytes(c.raw))
print('raw dump: %d bytes' % len(c.raw))
sys.exit(0 if (play_seen and command_sent and echo_found) else 1)
