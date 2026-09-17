/**
 * 关卡元数据与提示文案。
 *
 * 每关四层提示，逐层展开：谜语 → 方向 → 步骤 → 近答案。
 * 第 1 层不给任何操作信息，第 4 层基本等于答案——但到此为止了，
 * 真正的凭据仍然得玩家自己去取。
 */

export const ACTS = [
  { id: 1, title: '第一幕 · 观察者', note: '全部在浏览器里完成，不需要联网。' },
  { id: 2, title: '第二幕 · 越界', note: '开始和服务器打交道。' },
  { id: 3, title: '第三幕 · 离乡', note: '浏览器做不到了，搬到 Node。' }
]

export const SKILLS = [
  { key: 'console', label: '控制台', note: '开发者工具里那个能执行任意代码的地方' },
  { key: 'breakpoint', label: '断点调试', note: '在 Sources 里让执行停下来，读那一帧的局部变量' },
  { key: 'override', label: '函数重写', note: '函数在 JS 里只是值，可以被取出来、包一层、装回去' },
  { key: 'sentinel', label: '反调试脱困', note: '无限 debugger 与断点风暴的几种止法' },
  { key: 'tostring', label: 'toString 守护对抗', note: '源码指纹校验，以及怎么做一个无痕的 hook' },
  { key: 'network', label: '抓包与签名', note: '读请求体、还原签名拼接规则、自己重签' },
  { key: 'decrypt', label: '响应解密', note: '接口返回的是密文，得自己把它解开' },
  { key: 'node', label: 'Node 补环境', note: '把脚本搬出浏览器，缺什么补什么' },
  { key: 'ua', label: 'UA 硬门', note: '浏览器不允许改 User-Agent —— 有些墙绕不过去' },
  { key: 'pow', label: '工作量证明', note: '全协议还原 + 算力代价' }
]

export const GATES = [
  {
    n: 0,
    act: 1,
    name: '苏醒',
    brief: '让这套系统注意到你。',
    hints: [
      '这套系统不阻止你打开开发者工具。它在等你。',
      '页面在控制台里留了一份自我介绍。找到它，它会告诉你这个挑战是怎么构成的。',
      '打开 DevTools，刷新页面，看 Console 面板。然后执行 `HB.manifest()`。如果开场白没出现（少数环境下探针测不到），先执行一次 `HB._wake()`。',
      '`HB.manifest()` 返回的对象里有一个 `token` 字段，那就是第 0 关的凭据。执行 `HB.submit(0, token)`。'
    ]
  },
  {
    n: 1,
    act: 1,
    name: '停顿',
    brief: '有一个值只在执行的某一瞬间存在。',
    hints: [
      '源码是写给眼睛看的，运行态才是写给手看的。',
      '第 1 关的凭据在函数执行到一半时才存在，而且它不会被返回——它被一个单向函数吃掉了。',
      '在 Sources 面板里找到 `reversing/js/hb-gate-01.js`，在 `debugger` 那一行下断点，然后刷新页面。暂停后看右侧的 Scope → Local。',
      'Local 里那个 16 位 hex 的 `c` 就是凭据。复制出来，执行 `HB.submit(1, c)`。'
    ]
  },
  {
    n: 2,
    act: 1,
    name: '替换',
    brief: '看得见的东西可以被换掉。',
    hints: [
      '上一关你学会了看。这一关要学会改。',
      '站点通过一个注册表调用解码器。注册表是可以被写入的——而函数在 JS 里只是值。',
      '在 Console 里先把原来的取出来：`const orig = HB.pipeline.get("decoder")`。然后包一层再装回去：`HB.pipeline.register("decoder", t => { const r = orig(t); console.log(r); return r })`。最后触发一次：`HB.pipeline.run()`。',
      '打印出来的那串就是凭据。执行 `HB.submit(2, <那串>)`。'
    ]
  },
  {
    n: 3,
    act: 1,
    name: '哨兵',
    brief: '这一关会拦你，而且它会检查自己有没有被换掉。',
    hard: true,
    hints: [
      '从这里开始有人拦你了。',
      '有两件事要处理：一是断点风暴，二是源码指纹。任何一件没处理，你都会卡住。',
      '先止住风暴——`HB.disarm()` 可以直接让它停下，或者在 Sources 里对那行 `debugger` 右键选 Never pause here。至于指纹：`invoke` 每次执行前会用 `Function.prototype.toString` 检查自己的源码。',
      '三条路任选其一：① 让 `Function.prototype.toString` 撒谎，做一个无痕 hook；② 别碰 `invoke`，改去 hook 它依赖的 `HB.crypto.hmac`（底层没上锁）；③ 停下来把这文件读明白，自己把 `proofOf` 重算出来。拿到凭据后 `HB.submit(3, ...)`。'
    ]
  },
  {
    n: 4,
    act: 2,
    name: '握手',
    brief: '站点自己的请求失败了。你得替它重签一次。',
    hints: [
      '从这里开始，浏览器不再是唯一的战场。',
      '站点自己发了一个请求，但它用了过期的凭据链。Console 里会留下一个 `E_CREDENTIAL_STALE`。',
      '在 Network 面板里找到 `/api/reversing/v1/handshake`。看请求体——里面有个 `sig` 字段。签名对象是 `ts|client|nonce` 的字符串拼接，不是 JSON 原文。密钥是 `K4 = sha256(S0+S1+S2+S3)`。',
      '把 S0~S3 拼起来算出 K4，重算 `sig = hmac(K4, ts|client|nonce)`，用 curl 或 Node 发一次。响应里的 `ct` 用 K4 解密就是 S4。记入：`HB.setServerShard(4, S4)`。'
    ]
  },
  {
    n: 5,
    act: 2,
    name: '镜像',
    brief: '响应的长度，和它显示出来的长度不一样。',
    hints: [
      '服务器回了东西，但页面只显示了一小段。',
      '站点只解密了前 16 位就把剩下的丢掉了——而真碎片在后面。',
      '`/api/reversing/v1/attest` 的响应 `ct` 用 K4 可以完整解开。明文用 `|` 分成三段，真碎片在第二段。',
      '也可以 hook 站点的解密入口或者 `JSON.parse` 直接截获——但朴素 hook 会触发指纹检测（第 3 关学过怎么绕）。拿到后 `HB.setServerShard(5, S5)`。'
    ]
  },
  {
    n: 6,
    act: 3,
    name: '放逐',
    brief: '这个脚本拒绝在浏览器里运行。',
    hints: [
      '到这里，浏览器帮不了你了。',
      '第 6 关的脚本开头就把浏览器判了死刑，而且它依赖两个浏览器才有的全局对象。',
      '把 `reversing/js/hb-crypto.js` 和 `reversing/js/hb-gate-06.js` 一起存到本地，然后 `node hb-gate-06.js`，看它怎么炸。',
      '它缺 `document` 和 `localStorage`。在脚本最上面把环境补上：`globalThis.document = { cookie: "hb_uid=hbnode" }`、`globalThis.localStorage = { getItem: () => "7f3a91c2" }`。再跑一次就会打印出凭据。'
    ]
  },
  {
    n: 7,
    act: 3,
    name: '归化',
    brief: '浏览器有一个请求头，你改不了。',
    hints: [
      '浏览器有一个头，你在代码里怎么写都设不上去。',
      '这一关要求一个特定的 User-Agent。在 fetch 里写它会被静默忽略——这是浏览器故意的。',
      '用 Node 或 curl 发 `POST /api/reversing/v1/notarize`。请求头带 `User-Agent: hb-client/1.0`，签名是 `hmac(K6, ts|client)`，其中 `K6 = sha256(S6)`。',
      '响应里的 `ct` 用 K6 解密就是 S7。记入：`HB.setServerShard(7, S7)`。'
    ]
  },
  {
    n: 8,
    act: 3,
    name: '封印',
    brief: '最后一道门，要你证明你付了代价。',
    hints: [
      '最后一道门。',
      '要过它得同时满足两件事：一个工作量证明，和一份完整签名。在浏览器里会很痛苦——搬去 Node。',
      '先 `GET /api/reversing/v1/challenge` 拿 `challenge` / `window` / `bits`。找一个整数 `nonce`，让 `sha256(challenge + ":" + nonce)` 的前 `bits` 位是 0。然后用 `K8 = sha256(S7)` 签 `ts|window|nonce`，发 `POST /api/reversing/v1/terminal`。',
      '响应里的 `ct` 就是终章密文。把下面 8 个碎片按顺序拼起来算出 `K = sha256(S0+S1+...+S7)`，用它解密就是群号。把密文粘到页面下方的终章框里，页面会替你解。'
    ]
  }
]

export function gateByNumber(n) {
  return GATES.find((g) => g.n === n) ?? null
}

export const ACT1_GATES = GATES.filter((g) => g.act === 1)
