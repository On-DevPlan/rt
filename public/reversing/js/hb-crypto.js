/*!
 * hb-crypto — 纯 JS 密码学原语
 *
 * 为什么不用 WebCrypto：本站以纯 HTTP 提供（无 TLS、无域名），属于非安全上下文，
 * window.crypto.subtle 恒为 undefined。所有原语必须自实现。
 *
 * 本文件与 backend/src/rt_backend/reversing/crypto.py 必须逐字节一致。
 * 契约见 docs/reversing-protocol.md §1
 */
(function (root) {
  'use strict';

  // ---------------------------------------------------------------- 字节工具

  function utf8Bytes(str) {
    var out = [];
    for (var i = 0; i < str.length; i++) {
      var c = str.charCodeAt(i);
      if (c < 0x80) {
        out.push(c);
      } else if (c < 0x800) {
        out.push(0xc0 | (c >> 6), 0x80 | (c & 63));
      } else if (c >= 0xd800 && c <= 0xdbff && i + 1 < str.length) {
        var c2 = str.charCodeAt(i + 1);
        if (c2 >= 0xdc00 && c2 <= 0xdfff) {
          var cp = 0x10000 + ((c - 0xd800) << 10) + (c2 - 0xdc00);
          out.push(
            0xf0 | (cp >> 18),
            0x80 | ((cp >> 12) & 63),
            0x80 | ((cp >> 6) & 63),
            0x80 | (cp & 63)
          );
          i++;
        } else {
          out.push(0xe0 | (c >> 12), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63));
        }
      } else {
        out.push(0xe0 | (c >> 12), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63));
      }
    }
    return out;
  }

  function utf8String(bytes) {
    var out = '';
    for (var i = 0; i < bytes.length; ) {
      var b = bytes[i];
      if (b < 0x80) {
        out += String.fromCharCode(b);
        i += 1;
      } else if (b >= 0xc0 && b < 0xe0) {
        out += String.fromCharCode(((b & 31) << 6) | (bytes[i + 1] & 63));
        i += 2;
      } else if (b >= 0xe0 && b < 0xf0) {
        out += String.fromCharCode(
          ((b & 15) << 12) | ((bytes[i + 1] & 63) << 6) | (bytes[i + 2] & 63)
        );
        i += 3;
      } else {
        var cp =
          ((b & 7) << 18) |
          ((bytes[i + 1] & 63) << 12) |
          ((bytes[i + 2] & 63) << 6) |
          (bytes[i + 3] & 63);
        cp -= 0x10000;
        out += String.fromCharCode(0xd800 + (cp >> 10), 0xdc00 + (cp & 1023));
        i += 4;
      }
    }
    return out;
  }

  function asciiBytes(str) {
    var out = [];
    for (var i = 0; i < str.length; i++) {
      out.push(str.charCodeAt(i) & 0xff);
    }
    return out;
  }

  function hexToBytes(hex) {
    var out = [];
    for (var i = 0; i + 1 < hex.length; i += 2) {
      out.push(parseInt(hex.substr(i, 2), 16));
    }
    return out;
  }

  function bytesToHex(bytes) {
    var out = '';
    for (var i = 0; i < bytes.length; i++) {
      out += (bytes[i] < 16 ? '0' : '') + bytes[i].toString(16);
    }
    return out;
  }

  // ---------------------------------------------------------------- SHA-256

  var RC = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1,
    0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
    0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786,
    0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147,
    0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
    0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
    0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a,
    0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
    0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
  ];

  function rotr(x, n) {
    return (x >>> n) | (x << (32 - n));
  }

  function sha256Bytes(bytes) {
    var h = [
      0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
      0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19
    ];

    var len = bytes.length;
    var msg = bytes.slice();
    msg.push(0x80);
    while (msg.length % 64 !== 56) {
      msg.push(0);
    }
    var bitHi = Math.floor(len / 536870912);
    var bitLo = (len << 3) >>> 0;
    msg.push((bitHi >>> 24) & 0xff, (bitHi >>> 16) & 0xff, (bitHi >>> 8) & 0xff, bitHi & 0xff);
    msg.push((bitLo >>> 24) & 0xff, (bitLo >>> 16) & 0xff, (bitLo >>> 8) & 0xff, bitLo & 0xff);

    var w = new Array(64);

    for (var off = 0; off < msg.length; off += 64) {
      for (var i = 0; i < 16; i++) {
        w[i] =
          ((msg[off + i * 4] << 24) |
            (msg[off + i * 4 + 1] << 16) |
            (msg[off + i * 4 + 2] << 8) |
            msg[off + i * 4 + 3]) >>>
          0;
      }
      for (i = 16; i < 64; i++) {
        var s0 = rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >>> 3);
        var s1 = rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >>> 10);
        w[i] = (w[i - 16] + s0 + w[i - 7] + s1) | 0;
      }

      var a = h[0], b = h[1], c = h[2], d = h[3];
      var e = h[4], f = h[5], g = h[6], hh = h[7];

      for (i = 0; i < 64; i++) {
        var bigS1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
        var ch = (e & f) ^ (~e & g);
        var t1 = (hh + bigS1 + ch + RC[i] + w[i]) | 0;
        var bigS0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
        var maj = (a & b) ^ (a & c) ^ (b & c);
        var t2 = (bigS0 + maj) | 0;

        hh = g;
        g = f;
        f = e;
        e = (d + t1) | 0;
        d = c;
        c = b;
        b = a;
        a = (t1 + t2) | 0;
      }

      h[0] = (h[0] + a) | 0;
      h[1] = (h[1] + b) | 0;
      h[2] = (h[2] + c) | 0;
      h[3] = (h[3] + d) | 0;
      h[4] = (h[4] + e) | 0;
      h[5] = (h[5] + f) | 0;
      h[6] = (h[6] + g) | 0;
      h[7] = (h[7] + hh) | 0;
    }

    var out = [];
    for (i = 0; i < 8; i++) {
      out.push((h[i] >>> 24) & 0xff, (h[i] >>> 16) & 0xff, (h[i] >>> 8) & 0xff, h[i] & 0xff);
    }
    return out;
  }

  function sha256Hex(str) {
    return bytesToHex(sha256Bytes(utf8Bytes(str)));
  }

  // ---------------------------------------------------------------- HMAC-SHA256

  function hmacSha256Bytes(keyBytes, msgBytes) {
    var BLOCK = 64;
    var k = keyBytes.slice();
    if (k.length > BLOCK) {
      k = sha256Bytes(k);
    }
    while (k.length < BLOCK) {
      k.push(0);
    }

    var inner = [], outer = [];
    for (var i = 0; i < BLOCK; i++) {
      inner.push(k[i] ^ 0x36);
      outer.push(k[i] ^ 0x5c);
    }

    var innerHash = sha256Bytes(inner.concat(msgBytes));
    return sha256Bytes(outer.concat(innerHash));
  }

  // key 是 hex 字符串，按 ASCII 字节解释（契约 §1）
  function hmacSha256Hex(keyHex, msg) {
    return bytesToHex(hmacSha256Bytes(asciiBytes(keyHex), utf8Bytes(msg)));
  }

  // ---------------------------------------------------------------- 流密码

  // keystream(key, n) = HMAC-SHA256(key, "HB" + i) 逐块拼接
  function keystreamBytes(keyHex, n) {
    var out = [];
    var i = 0;
    while (out.length < n) {
      var block = hmacSha256Bytes(asciiBytes(keyHex), utf8Bytes('HB' + i));
      for (var j = 0; j < block.length && out.length < n; j++) {
        out.push(block[j]);
      }
      i++;
    }
    return out;
  }

  // 加密：明文 → hex 密文
  function encrypt(keyHex, text) {
    var pt = utf8Bytes(text);
    var ks = keystreamBytes(keyHex, pt.length);
    var ct = [];
    for (var i = 0; i < pt.length; i++) {
      ct.push(pt[i] ^ ks[i]);
    }
    return bytesToHex(ct);
  }

  // 解密：hex 密文 → 明文
  function decrypt(keyHex, hexCipher) {
    var ct = hexToBytes(hexCipher);
    var ks = keystreamBytes(keyHex, ct.length);
    var pt = [];
    for (var i = 0; i < ct.length; i++) {
      pt.push(ct[i] ^ ks[i]);
    }
    return utf8String(pt);
  }

  // ---------------------------------------------------------------- 导出

  root.HB = root.HB || {};
  root.HB.crypto = {
    sha256: sha256Hex,
    hmac: hmacSha256Hex,
    encrypt: encrypt,
    decrypt: decrypt,
    keystream: keystreamBytes,
    _utf8Bytes: utf8Bytes,
    _utf8String: utf8String,
    _hexToBytes: hexToBytes,
    _bytesToHex: bytesToHex
  };
})(typeof globalThis !== 'undefined' ? globalThis : this);
