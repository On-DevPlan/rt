# F12 逆向挑战 — 协议契约（P0，冻结）

> 这份文档是前后端唯一的真相来源。任何字段名、拼接顺序、编码方式的改动都必须先改这里。
> 版本：`v1`　前缀：`/api/reversing/v1`

---

## 0. 威胁模型与前提

- **玩家只能看到部署后的站点**：前端产物 + API 请求/响应。**看不到本仓库源码。**
- 因此服务器侧常量（主盐、服务端碎片）写在 `core/config.py` 与 `handbook/service.py` 里是允许的。
  ⚠️ **若本仓库将来公开**，`reversing_master_salt` 必须改为纯环境变量注入，否则老手可直接推出 S4/S5/S7。
- 服务器**不落盘任何人**：无账号、无进度、无排行榜、无会话表。

---

## 1. 密码学原语

**不使用 AES / WebCrypto**——部署是纯 HTTP（`nginx.conf` 只有 `listen 80`，容器映射 `-p 81:80`，无域名无 TLS），
属**非安全上下文**，`window.crypto.subtle` 恒为 `undefined`。

全部原语自实现，前端（`public/reversing/js/hb-crypto.js`）与后端（`backend/.../reversing/crypto.py`）**必须逐字节一致**。

| 原语 | 定义 |
|---|---|
| `sha256_hex(s)` | UTF-8 编码后 SHA-256，输出 **64 位小写 hex** |
| `hmac_sha256_hex(key, msg)` | `key` 按 **ASCII 字节**解释（它本身是 hex 字符串），`msg` 按 UTF-8。输出 64 位小写 hex |
| `keystream(key, n)` | `HMAC-SHA256(key, "HB" + i)` 逐块拼接（`i` 为十进制计数，从 0 起），共 `n` 字节 |
| `xor_stream(key, pt_bytes)` | `ct[i] = pt[i] XOR keystream(key, len(pt))[i]` |

**所有密文/消息在线路上的编码一律为小写 hex。** 不使用 base64（避免字母表与 padding 歧义）。

---

## 2. 碎片模型

共 **8 个碎片** `S0..S7`（每个 16 位小写 hex）+ **1 个终章** `G8`。

```
S_n = sha256_hex("hb:shard:" + n + ":" + PROOF_n).slice(0, 16)
K   = sha256_hex(S0 + S1 + S2 + S3 + S4 + S5 + S6 + S7)      // 拼接无分隔符
final.blob = xor_stream(K, utf8(<ANSWER>))                     // 静态入库，只存密文
```

> `<ANSWER>` 是群号明文。**它不在本仓库的任何文件里**——只作为 `REVERSING_ANSWER`
> 环境变量在生成脚本运行的那一瞬间存在。生成方式见 §7。

| 碎片 | 关卡 | 来源 | PROOF 从哪来 |
|---|---|---|---|
| `S0` | G0 苏醒 | 本地 | 控制台 banner 给出的 token |
| `S1` | G1 停顿 | 本地 | `HB.stage1()` 内被 `debugger` 拦下的局部变量 `c` |
| `S2` | G2 替换 | 本地 | hook `HB.pipeline` 的 decoder 后捕获的明文 |
| `S3` | G3 哨兵 | 本地 | 被 `toString` 守护函数的实参 |
| `S4` | G4 握手 | **服务端** | `/handshake` 验签通过后在 `ct` 里下发（用 `K4` 加密） |
| `S5` | G5 镜像 | **服务端** | `/attest` 响应 `ct` 解密后的完整明文 |
| `S6` | G6 放逐 | 本地 | `hb-gate-06.js` 在 Node 中补环境跑通的输出 |
| `S7` | G7 归化 | **服务端** | `/notarize` 响应 `ct` 解密（用 `K6` 加密） |

**派生密钥**（玩家侧用已收集的碎片自行算出）：

```
K4 = sha256_hex(S0 + S1 + S2 + S3)     // G4 签名密钥 & S4/S5 的解密密钥
K6 = sha256_hex(S6)                     // G7 签名密钥 & S7 的解密密钥
K8 = sha256_hex(S7)                     // G8 签名密钥
K  = sha256_hex(S0+..+S7)               // 终章解密密钥
```

**服务器只持有 S0..S7 的副本**（用于验签与生成响应密文），**不持有 `K`**，**不知道答案**。

---

## 3. 无状态设计

不签发票据、不建会话表、不落盘。

每个请求自带 `ts`（Unix 秒）。服务器用 **±120 秒时间窗**判重放，超出即 `401`。
`nonce` 为客户端生成的 16 位 hex，仅用于让签名不可复用。

**签名对象是显式字符串拼接，绝不是 JSON 原文。**
这是刻意的：Python 与 JS 的 JSON 序列化在键序、空格、浮点格式上不一致，若签 JSON 原文，
玩家会永远卡在"我明明算对了"。规则必须在协议层扼杀。

---

## 4. 端点契约

### 4.1 `GET /api/reversing/v1/challenge`

G8 PoW 用。无请求体。

```json
200 { "challenge": "<32 hex>", "bits": 20, "window": 28901234 }
```

- `challenge = hmac_sha256_hex(MASTER_SALT, "challenge:" + window).slice(0, 32)`
- `window = ts // 120`（服务器下发，避免客户端时钟漂移）
- 服务器接受 `window` 与 `window - 1` 两档，超出即 `401`

### 4.2 `POST /api/reversing/v1/handshake` — G4

```json
// req
{ "ts": 1758000000, "client": "hb-web/1.0", "nonce": "<16 hex>", "sig": "<64 hex>" }
// sig = hmac_sha256_hex(K4, ts + "|" + client + "|" + nonce)

// 200
{ "ct": "<hex>" }     // = xor_stream(K4, utf8(S4))
```

> 站点自己发这个请求时**故意用错误的 sig**（模拟凭据链过期），控制台打印 `E_CREDENTIAL_STALE`。
> 玩家必须自己算出 `K4` 重签。

### 4.3 `POST /api/reversing/v1/attest` — G5

```json
// req（同 handshake 结构，仍用 K4 签名）
{ "ts": ..., "client": "hb-web/1.0", "nonce": "<16 hex>", "sig": "<64 hex>" }
// sig = hmac_sha256_hex(K4, ts + "|" + client + "|" + nonce)

// 200
{ "ct": "<hex>" }     // = xor_stream(K4, utf8(PAYLOAD_5))
// PAYLOAD_5 = DECOY_16 + "|" + S5 + "|" + TAIL_16
```

> 站点**只解密并消费前 16 位**（即 `DECOY_16`），其余丢弃。玩家必须自己解全文。

### 4.4 `POST /api/reversing/v1/notarize` — G7

```json
// req
{ "ts": ..., "client": "hb-node/1.0", "sig": "<64 hex>" }
// sig = hmac_sha256_hex(K6, ts + "|" + client)
// 必需请求头：User-Agent: hb-client/1.0

// 200
{ "ct": "<hex>" }     // = xor_stream(K6, utf8(S7))
```

> **浏览器无法设置 `User-Agent`**（forbidden header name），`fetch`/XHR 会静默忽略。
> 这一关在数学上强制玩家离开浏览器。`User-Agent` 的值本身不是秘密（提示会给出），
> 真正的墙是"浏览器设不了"。
> UA 不匹配 → `403 {"code":403,"msg":"客户端未被授权","trace_id":"..."}`

### 4.5 `POST /api/reversing/v1/terminal` — G8

```json
// req
{ "ts": ..., "window": 28901234, "nonce": "<int>", "client": "hb-node/1.0", "sig": "<64 hex>" }
// PoW: sha256_hex(challenge + ":" + nonce) 的前 bits 位必须是 0
// sig = hmac_sha256_hex(K8, ts + "|" + window + "|" + nonce)

// 200
{ "ct": "<hex final.blob>" }
```

### 4.6 蜜罐 `ANY /api/reversing/v1/admin/*`

恒返回：

```json
403 { "code": 403, "msg": "权限不足", "trace_id": "<12 hex>" }
```

---

## 5. 统一错误 envelope

所有失败响应（除蜜罐外）形状一致，**不透露任何方向**：

```json
{ "code": 401, "msg": "凭据校验失败", "trace_id": "a3f9c1d2e4b7" }
```

`trace_id` 取自 `core/logging.get_request_id()`（该中间件已存在并回写 `X-Request-ID` 响应头）。

| code | msg |
|---|---|
| `400` | `请求格式不合法` |
| `401` | `凭据校验失败` |
| `403` | `客户端未被授权` |
| `429` | `请求过于频繁` |

**失败响应绝不包含**"哪一步错了""应该用哪个 key"之类的提示——否则签名校验会退化成暴力破解的指南针。

---

## 6. 前端谜题文件（`public/reversing/`，不进打包器）

经典 `<script src>` 注入，DevTools Sources 里以**独立文件条目**出现（不是 `VM123` eval），保证可断点、可读。

| 文件 | 职责 |
|---|---|
| `js/hb-crypto.js` | `sha256` / `hmac` / `keystream` / `xor_stream`，纯 JS，可读 |
| `js/hb-core.js` | DevTools 探针、console banner、`HB.vault` / `HB.submit` / `HB.manifest` |
| `js/hb-gate-01.js` | `HB.stage1()` — debugger 断点关 |
| `js/hb-gate-02.js` | `HB.pipeline` 注册表 + 默认 decoder |
| `js/hb-gate-03.js` | 哨兵：`setInterval` 无限 debugger + `toString` 守护 |
| `js/hb-gate-05.js` | 响应解密 + 朴素 hook 检测 |
| `js/hb-gate-06.js` | `E_ENV` 环境门 + 补环境陷阱 |
| `js/hb-node-harness.js` | 终章 Node 侧骨架（给结构不给答案） |

统一命名空间：`globalThis.HB`。

**逃生舱**：`HB.stage3.disarm()`、`/reversing?debug=1`（绕过全部关卡，直接展示所有碎片与提示）。

---

## 7. 常量表

服务器的 `reversing_master_salt` 见 `core/config.py`。
`.tool/reversing-gen/gen.mjs` 与服务器**必须使用同一个盐**，否则 `final.blob` 无法解密。

本地关卡的 `PROOF_n` 定义在各 `public/reversing/js/hb-gate-*.js` 内，服务器侧在
`backend/src/rt_backend/reversing/service.py` 保留同样一份副本用于验签。
