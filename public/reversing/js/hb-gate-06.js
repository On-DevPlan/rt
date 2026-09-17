/*!
 * hb-gate-06 — 放逐
 *
 * 到这里浏览器帮不了你了。
 *
 * 这个脚本拒绝在浏览器里运行，而且它依赖两个浏览器才有的全局对象。
 * 想拿到凭据，你得：
 *
 *   1. 把 hb-crypto.js 和这个文件一起存到本地；
 *   2. node hb-gate-06.js —— 看它怎么炸；
 *   3. 读懂它缺什么，把环境补齐（globalThis.document / globalThis.localStorage）；
 *   4. 再跑一次。
 *
 * 这就是补环境。之后你会一直用到它。
 */
(function (root) {
  'use strict';

  var HB = root.HB;
  var SEED_6 = '7f3a91c2';
  var COOKIE = 'hb_uid=hbnode';

  var IN_BROWSER = typeof window !== 'undefined';

  function proofOf(cookie) {
    return HB.crypto.sha256('hb:g6:' + SEED_6 + ':' + cookie).slice(0, 16);
  }

  /**
   * 只有离开浏览器才跑得起来。
   * 返回 16 位 hex 凭据。
   */
  function run() {
    if (IN_BROWSER) {
      throw new Error('E_ENV: browser context rejected');
    }

    // 这两行在 Node 里会直接 ReferenceError——除非你把环境补上。
    var doc = document;
    var store = localStorage;

    if (store.getItem('hb.seed') !== SEED_6) {
      throw new Error('E_ENV: seed mismatch');
    }
    if (String(doc.cookie).indexOf(COOKIE) === -1) {
      throw new Error('E_ENV: cookie unavailable');
    }

    return proofOf(doc.cookie);
  }

  HB.stage6 = {
    run: run,
    source: '/reversing/js/hb-gate-06.js'
  };

  var gate6 = {
    // 浏览器侧只认结果，不认过程——过程得在 Node 里完成。
    check: function (p) {
      return p === proofOf(COOKIE);
    }
  };
  if (HB._debugMode) {
    gate6.expected = function () {
      return proofOf(COOKIE);
    };
  }
  HB._register(6, gate6);

  // 直接 `node hb-gate-06.js` 时把凭据打出来
  if (!IN_BROWSER && typeof module !== 'undefined' && module.exports) {
    try {
      root.console.log('[hb] gate-06 proof =', run());
    } catch (e) {
      root.console.log('[hb] ' + e.message + ' — 环境还没补全。');
    }
  }
})(typeof globalThis !== 'undefined' ? globalThis : this);
