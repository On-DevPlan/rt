/*!
 * hb-gate-01 — 停顿
 *
 * 这一关要教的东西只有一件：源码是静态的，运行态才是活的。
 * 凭据 c 只存在于 stage1 执行时的那一帧里。它不被返回、不被存储、
 * 被单向函数吃掉之后就再也拿不回来了。
 *
 * 想拿到它，你有两条路：
 *   1. 在下面那行 debugger 上停下来，从 Scope 面板里把 c 读出来；
 *   2. 把 _mix 抄走，自己把 SEED_1 喂进去重算一遍（能行，但比第 1 条累）。
 */
(function (root) {
  'use strict';

  var HB = root.HB;

  // 四轮扩散的混合函数。输出 16 位 hex。
  function _mix(seed) {
    var a = 0x1505;
    var b = 0x811c;
    var i;
    for (i = 0; i < seed.length; i++) {
      var ch = seed.charCodeAt(i);
      a = (Math.imul(a, 33) + ch) | 0;
      b = Math.imul(b ^ ch, 0x01000193);
    }
    var out = '';
    for (i = 0; i < 4; i++) {
      a = Math.imul(a ^ (a >>> 13), 0x5bd1e995);
      b = ((b + Math.imul(b, 8)) ^ (a >>> 7)) | 0;
      out += ('0000000' + ((a ^ b) >>> 0).toString(16)).slice(-8).slice(0, 4);
    }
    return out;
  }

  var SEED_1 = 'hb:g1:seed:' + HB._boot;

  function proofOf() {
    var t1 = _mix(SEED_1);
    var t2 = _mix(t1 + '|' + SEED_1);
    return _mix(t2 + '|' + t1);
  }

  /**
   * 计算一次握手确认。
   * 返回的对象里只有单向摘要——c 本身出不去。
   */
  HB.stage1 = function () {
    var c = proofOf();

    debugger; // ← 就是这里。暂停，然后在 Scope 里找 c。

    return { ack: HB.crypto.hmac(c, 'hb:g1:ack'), build: HB._boot };
  };

  var gate1 = {
    check: function (p) {
      return p === proofOf();
    }
  };
  if (HB._debugMode) {
    gate1.expected = proofOf;
  }
  HB._register(1, gate1);
})(typeof globalThis !== 'undefined' ? globalThis : this);
