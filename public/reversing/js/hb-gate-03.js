/*!
 * hb-gate-03 — 哨兵
 *
 * 前两关只要你"看"和"改"。这一关开始有人拦你。
 *
 * 拦你的手段有两个：
 *   1. arm() 之后每 137 毫秒触发一次 debugger。断点风暴会让你没法在
 *      控制台里干活。要么找到那个 interval 把它掐了，要么在 Sources 里
 *      对着那一行右键 → Never pause here。
 *   2. invoke() 每次执行前会检查自己的源码指纹。你如果直接把
 *      HB.stage3.invoke 换成一个新函数，Function.prototype.toString
 *      拿到的就是新函数的源码——指纹没了，判定篡改。
 *
 * 有若干条路可以过，都不是死路：
 *   a. 掐掉哨兵，然后把这文件读明白，自己把 proofOf 重算出来；
 *   b. 不碰 invoke，改去 hook 它依赖的 HB.crypto.hmac——底层没上锁；
 *   c. 让 Function.prototype.toString 撒个谎，做一个无痕 hook。
 *
 * 任何一条都成立。
 */
(function (root) {
  'use strict';

  var HB = root.HB;
  var MARK = 'HB:NATIVE';

  var SEED_3 = 'hb:g3:' + HB._boot;
  var timer = null;

  function _mix3(seed) {
    var h = 0xcbf29ce4 | 0;
    for (var i = 0; i < seed.length; i++) {
      h = Math.imul(h ^ seed.charCodeAt(i), 0x01000193);
    }
    var out = '';
    for (var r = 0; r < 4; r++) {
      h = Math.imul(h ^ (h >>> 15), 0x2545f491);
      out += ('0000000' + (h >>> 0).toString(16)).slice(-8).slice(0, 4);
    }
    return out;
  }

  function proofOf() {
    return _mix3(SEED_3 + '|' + _mix3(HB._boot));
  }

  // 源码指纹比对
  function intact() {
    var src = Function.prototype.toString.call(api.invoke);
    return src.indexOf(MARK) !== -1;
  }

  function _consume(v) {
    return HB.crypto.hmac(v, 'hb:g3:ack');
  }

  var api = {
    /** 上哨兵：断点风暴。 */
    arm: function () {
      if (timer !== null) {
        return false;
      }
      timer = setInterval(function () {
        debugger;
      }, 137);
      HB._setArmed(true);
      return true;
    },

    /** 撤哨兵。随时可用，没人拦你。 */
    disarm: function () {
      if (timer !== null) {
        clearInterval(timer);
        timer = null;
      }
      HB._setArmed(false);
      return true;
    },

    /** 受守护的调用。 */
    invoke: function () {
      /*HB:NATIVE*/
      if (!intact()) {
        return HB._fail('E_TAMPER');
      }
      return _consume(proofOf());
    },

    status: function () {
      return { armed: timer !== null, intact: intact() };
    }
  };

  HB.stage3 = api;

  var gate3 = {
    check: function (p) {
      return p === proofOf();
    },
    disarm: function () {
      api.disarm();
    }
  };
  if (HB._debugMode) {
    gate3.expected = proofOf;
  }
  HB._register(3, gate3);
})(typeof globalThis !== 'undefined' ? globalThis : this);
