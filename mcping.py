# -*- coding: utf-8 -*-
"""MC 1.7+ status ping probe: handshake + status request + JSON response."""
import socket
import struct
import json
import sys


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


def read_varint(s):
    num = 0
    shift = 0
    while True:
        b = s.recv(1)
        if not b:
            raise ConnectionError('eof')
        v = b[0]
        num |= (v & 0x7F) << shift
        if not (v & 0x80):
            return num
        shift += 7


def ping(host, port, proto=775):
    with socket.create_connection((host, port), timeout=6) as s:
        # handshake
        hostb = host.encode()
        payload = varint(0) + varint(proto) + varint(len(hostb)) + hostb + struct.pack('>H', port) + varint(1)
        s.sendall(varint(len(payload)) + payload)
        # status request
        s.sendall(varint(1) + b'\x00')
        # response: packet length varint, then packet id 0, then string
        pkt_len = read_varint(s)
        data = b''
        while len(data) < pkt_len:
            chunk = s.recv(pkt_len - len(data))
            if not chunk:
                raise ConnectionError('eof mid packet')
            data += chunk
        assert data[0] == 0, 'unexpected packet id %d' % data[0]
        sstr_len = read_varint_safe(data[1:])
        # decode: the remaining bytes are a varint length + string
        pos = 0
        slen = 0
        shift = 0
        while True:
            v = data[1 + pos]
            slen |= (v & 0x7F) << shift
            pos += 1
            if not (v & 0x80):
                break
            shift += 7
        s = data[1 + pos:1 + pos + slen]
        return json.loads(s.decode('utf-8'))


def read_varint_safe(_):
    pass


if __name__ == '__main__':
    host = sys.argv[1]
    port = int(sys.argv[2])
    try:
        info = ping(host, port)
        print('OK host=%s:%d' % (host, port))
        print('  version: %s (protocol %s)' % (info.get('version', {}).get('name'), info.get('version', {}).get('protocol')))
        desc = info.get('description', {})
        print('  motd:', desc.get('text') or desc.get('extra', ''))
        print('  players: %s/%s' % (info.get('players', {}).get('online'), info.get('players', {}).get('max')))
        print('  mods:', info.get('modinfo'))
    except Exception as e:
        print('FAIL %s:%d -> %r' % (host, port, e))
        sys.exit(1)
