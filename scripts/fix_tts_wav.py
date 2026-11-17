#!/usr/bin/env python3
"""修 TTS 返回的 wav 头。

有些 TTS 服务返回的 wav 里，RIFF/data 长度写成 0xFFFFFFFF。
ffmpeg 只会警告一句，Windows 的播放器直接判"不是有效 wav"。
这个脚本把长度改回真实值，其它字节不动。

用法：python fix_tts_wav.py <file.wav> [输出.wav]
不给输出就原地修。
"""
import struct
import sys


def fix(buf: bytes) -> bytes:
    if buf[0:4] != b"RIFF":
        return buf
    total = len(buf)
    pos = 12
    while pos + 8 <= total:
        cid = buf[pos:pos + 4]
        size = struct.unpack("<I", buf[pos + 4:pos + 8])[0]
        if size == 0xFFFFFFFF:
            size = total - pos - 8
        if cid == b"data":
            out = bytearray(buf[:pos + 8 + size])
            struct.pack_into("<I", out, pos + 4, size)
            struct.pack_into("<I", out, 4, len(out) - 8)
            return bytes(out)
        pos += 8 + size + (size % 2)
    return buf


def main() -> None:
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else src
    with open(src, "rb") as f:
        data = fix(f.read())
    with open(dst, "wb") as f:
        f.write(data)
    print("fixed", dst, len(data), "bytes")


if __name__ == "__main__":
    main()
