/*!
 * hb-core — 挑战内核
 *
 * 负责：DevTools 探针、控制台开场、碎片金库、关卡提交分发、逃生舱。
 * 关卡逻辑分别在 hb-gate-*.js 中注册。
 *
 * 契约见 docs/reversing-protocol.md §6
 */
(function (root) {
  'use strict';

  var HB = (root.HB = root.HB || {});
  if (HB.__core) {
    return;
  }
  HB.__core = true;

  if (!HB.crypto) {
    throw new Error('[hb] hb-crypto.js must be loaded before hb-core.js');
  }

  // ------------------------------------------------------------ 常量

  // 构建号。也出现在页面页脚。
  HB._boot = '7f3a91c2';

  // 封印用密钥。不是秘密——只是让门口的值不要以明文乱飘。
  HB._k = 'b0a1c2d3e4f5061728394a5b6c7d8e9f';

  // G0 的令牌
  var PROOF_0 = '0bs3rv3r-4w4k3';

  var STORE_KEY = 'hb.v1.state';
  var LOCAL_GATES = [0, 1, 2, 3, 6];
  var ALL_GATES = [0, 1, 2, 3, 4, 5, 6, 7];

  // ------------------------------------------------------------ 状态

  var state = {
    awake: false,
    shards: {},       // n -> "16 hex"
    proofs: {},       // n -> proof 字符串（本地关）
    armed: false,     // G3 哨兵是否在跑
    tamper: false,    // 是否检测到篡改
    debug: /[?&]debug=1\b/.test(root.location ? root.location.search : '')
  };

  // 关卡文件在 hb-core 之后加载，它们靠这个标记决定要不要暴露 expected()。
  // 正常模式下 _gates[n].expected 是 undefined —— 后门只在 ?debug=1 时存在。
  HB._debugMode = state.debug;

  var listeners = [];

  function emit() {
    persist();
    for (var i = 0; i < listeners.length; i++) {
      try {
        listeners[i](snapshot());
      } catch (e) {
        /* 监听者自己炸了不该拖垮内核 */
      }
    }
  }

  function snapshot() {
    var gates = {};
    ALL_GATES.forEach(function (n) {
      gates[n] = {
        done: Object.prototype.hasOwnProperty.call(state.shards, n),
        local: LOCAL_GATES.indexOf(n) !== -1
      };
    });
    return {
      build: HB._boot,
      awake: state.awake,
      armed: state.armed,
      tamper: state.tamper,
      debug: state.debug,
      gates: gates,
      shards: Object.assign({}, state.shards)
    };
  }

  function persist() {
    // debug 模式不落盘：后门只在当次加载有效，不能把进度永久污染掉。
    // 下次带 ?debug=1 打开时会重新补齐，代价可忽略。
    if (state.debug) {
      return;
    }
    try {
      root.localStorage.setItem(
        STORE_KEY,
        JSON.stringify({ shards: state.shards, proofs: state.proofs, awake: state.awake })
      );
    } catch (e) {
      /* 隐私模式 / 配额满：静默降级为纯内存 */
    }
  }

  function restore() {
    try {
      var raw = root.localStorage.getItem(STORE_KEY);
      if (!raw) {
        return;
      }
      var saved = JSON.parse(raw);
      if (saved && typeof saved === 'object') {
        state.shards = saved.shards || {};
        state.proofs = saved.proofs || {};
        state.awake = !!saved.awake;
      }
    } catch (e) {
      /* 坏数据当作没有 */
    }
  }

  // ------------------------------------------------------------ 碎片

  // 契约 §2：S_n = sha256("hb:shard:" + n + ":" + PROOF_n)[:16]
  function shardOf(n, proof) {
    return HB.crypto.sha256('hb:shard:' + n + ':' + proof).slice(0, 16);
  }

  // K = sha256(S0 + S1 + ... + S7)
  function assembleKey() {
    var parts = [];
    for (var i = 0; i < ALL_GATES.length; i++) {
      var s = state.shards[ALL_GATES[i]];
      if (!s) {
        return null;
      }
      parts.push(s);
    }
    return HB.crypto.sha256(parts.join(''));
  }

  // ------------------------------------------------------------ 关卡注册与提交

  var gates = {};

  /**
   * 关卡文件调用它注册自己。
   * def.check(proof) -> boolean   校验玩家提交的凭据
   * def.arm()                     可选，关卡被激活时调用
   * def.disarm()                  可选
   */
  HB._register = function (n, def) {
    gates[n] = def || {};
  };

  // 第 0 关：凭据就是开场白里那个 token。门槛故意设得很低——
  // 它教的是"控制台里有东西"，不是"破解"。
  var gate0 = {
    check: function (p) {
      return p === PROOF_0;
    }
  };
  if (HB._debugMode) {
    gate0.expected = function () {
      return PROOF_0;
    };
  }
  HB._register(0, gate0);

  HB.submit = function (n, proof) {
    n = Number(n);
    proof = String(proof == null ? '' : proof).trim();

    if (LOCAL_GATES.indexOf(n) === -1) {
      return { ok: false, reason: 'E_NOT_LOCAL', msg: '该关的碎片不来自本地提交' };
    }
    if (state.shards[n] && !state.debug) {
      return { ok: true, reason: 'E_ALREADY', shard: state.shards[n] };
    }
    if (!gates[n] || typeof gates[n].check !== 'function') {
      return { ok: false, reason: 'E_UNKNOWN_GATE', msg: '关卡未注册' };
    }

    var ok = false;
    try {
      ok = gates[n].check(proof) === true;
    } catch (e) {
      return { ok: false, reason: 'E_INTERNAL', msg: String(e && e.message) };
    }

    if (!ok) {
      return { ok: false, reason: 'E_INVALID_PROOF', msg: '凭据校验失败' };
    }

    state.proofs[n] = proof;
    state.shards[n] = shardOf(n, proof);
    emit();
    return { ok: true, shard: state.shards[n] };
  };

  // 服务端关（4 / 5 / 7）由外壳在协议成功后调用
  HB.setServerShard = function (n, shard) {
    n = Number(n);
    if (LOCAL_GATES.indexOf(n) !== -1) {
      return false;
    }
    if (!/^[0-9a-f]{16}$/.test(String(shard || ''))) {
      return false;
    }
    state.shards[n] = String(shard);
    emit();
    return true;
  };

  // ------------------------------------------------------------ 逃生舱

  HB.disarm = function () {
    if (gates[3] && typeof gates[3].disarm === 'function') {
      gates[3].disarm();
    }
    state.armed = false;
    emit();
    return true;
  };

  HB.reset = function () {
    state.shards = {};
    state.proofs = {};
    HB.disarm();
    emit();
    return true;
  };

  // debug=1：本地关直接补齐。服务端关（4/5/7）仍要走协议——
  // 那三片只存在于服务器，客户端变不出来，后门也不该在生产环境里变出来。
  function applyDebug() {
    if (!state.debug) {
      return;
    }
    HB.disarm();
    LOCAL_GATES.forEach(function (n) {
      if (state.shards[n] || !gates[n] || typeof gates[n].expected !== 'function') {
        return;
      }
      var proof = gates[n].expected();
      state.proofs[n] = proof;
      state.shards[n] = shardOf(n, proof);
    });
  }

  // ------------------------------------------------------------ 事件

  HB.on = function (fn) {
    listeners.push(fn);
    return function () {
      var i = listeners.indexOf(fn);
      if (i !== -1) {
        listeners.splice(i, 1);
      }
    };
  };

  HB.state = snapshot;
  HB.key = assembleKey;

  // ------------------------------------------------------------ DevTools 探针

  function probe() {
    var t0 = root.performance ? root.performance.now() : Date.now();
    // 打开开发者工具时，这一行会让执行停住；没打开时它是个空操作。
    // 差值就是开发者工具是否在场的直接证据。
    debugger;
    var dt = (root.performance ? root.performance.now() : Date.now()) - t0;
    if (dt > 60) {
      return true;
    }
    // 兜底：停靠式开发者工具会吃掉视口
    var dw = (root.outerWidth || 0) - (root.innerWidth || 0);
    var dh = (root.outerHeight || 0) - (root.innerHeight || 0);
    return dw > 160 || dh > 160;
  }

  function banner() {
    var css = 'color:#1e7a5d;font-weight:700';
    var dim = 'color:#66584a';
    root.console.log('%c╔══════════════════════════════════════════════╗', css);
    root.console.log('%c║  hb/0.9 — 外部观察者已接入                   ║', css);
    root.console.log('%c╚══════════════════════════════════════════════╝', css);
    root.console.log('%c你打开了开发者工具。这套系统不阻止你——它在等你。', dim);
    root.console.log('%c\n先看看它是怎么构成的：', dim);
    root.console.log('%c  HB.manifest()', 'color:#a65131;font-weight:700');
    root.console.log('%c\n提交凭据：%cHB.submit(n, proof)', dim, 'color:#a65131');
    root.console.log('%c装不下了就喊一声：%cHB.disarm()', dim, 'color:#a65131');
    root.console.log('%c\n构建号 %s', dim, HB._boot);
  }

  /**
   * 手动唤醒。
   *
   * 探针靠 debugger 的停顿耗时和视口差来判断开发者工具是否在场——
   * 绝大多数浏览器都测得到，但要是你在某个环境下没看到开场白，
   * 执行这一行补上。它不改变任何关卡的可解性，只补个招呼。
   */
  HB._wake = function () {
    state.awake = true;
    banner();
    emit();
    return true;
  };

  HB.manifest = function () {
    var s = snapshot();
    return {
      build: HB._boot,
      awake: s.awake,
      token: PROOF_0,
      localGates: LOCAL_GATES.slice(),
      serverGates: [4, 5, 7],
      finalGate: 8,
      gates: s.gates,
      debug: s.debug,
      note: 'token 只对第 0 关有效。其余关卡的凭据得自己去源码里取。',
      serverShards: 'S4 / S5 / S7 只存在于服务器。拿到之后用 HB.setServerShard(n, shard) 记入。'
    };
  };

  // ------------------------------------------------------------ 引导

  HB._setArmed = function (v) {
    state.armed = !!v;
    emit();
  };

  HB._fail = function (code) {
    state.tamper = true;
    emit();
    root.console.warn(
      '%c[hb] %s',
      'color:#a65131;font-weight:700',
      code + ' — 完整性校验未通过，本关的凭据已被作废。'
    );
    root.console.warn('%c哨兵还在跑。HB.disarm() 可以让它停下。', 'color:#66584a');
    return null;
  };

  HB._gates = gates;

  function boot() {
    restore();
    state.awake = probe();
    if (state.awake) {
      banner();
    }
    applyDebug();
    emit();
  }

  // 关卡文件先注册，再启动
  HB._bootFn = boot;
})(typeof globalThis !== 'undefined' ? globalThis : this);
