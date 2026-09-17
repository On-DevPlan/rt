/*!
 * hb-gate-02 — 替换
 *
 * 上一关你学会了"看"。这一关要教的是"改"。
 *
 * 站点通过一个注册表调用解码器。run() 的返回值是单向摘要，
 * 明文在 _consume 里被吃掉就没了——你盯不住它。
 *
 * 但那个解码器是可以被换掉的。函数在 JS 里只是值。
 * 把原来的取出来，包一层，装回去：
 *
 *   const orig = HB.pipeline.get('decoder');
 *   HB.pipeline.register('decoder', (t) => {
 *     const r = orig(t);
 *     console.log('decoder ->', r);
 *     return r;
 *   });
 *   HB.pipeline.run();
 */
(function (root) {
  'use strict';

  var HB = root.HB;

  function _mix2(seed, salt) {
    var h = 0x1f2e3d4c;
    for (var i = 0; i < seed.length; i++) {
      h = Math.imul(h ^ seed.charCodeAt(i), 0x85ebca6b);
      h = (h << 13) | (h >>> 19);
    }
    var out = '';
    for (var r = 0; r < 4; r++) {
      h = (h + Math.imul(h, 32)) ^ (h >>> 11);
      out += ('0000000' + ((h ^ salt) >>> 0).toString(16)).slice(-8).slice(0, 4);
    }
    return out;
  }

  var SEED_2 = 'hb:g2:token:' + HB._boot;
  var SALT_2 = 0x9e3779b9;

  function decode(token) {
    return _mix2(token, SALT_2) + _mix2(token.split('').reverse().join(''), SALT_2).slice(0, 8);
  }

  // 单向消费：把明文嚼碎，谁都别想从返回值里还原它。
  function _consume(plain) {
    return HB.crypto.hmac(plain, 'hb:g2:ack');
  }

  var registry = {};

  HB.pipeline = {
    register: function (name, fn) {
      registry[name] = fn;
      return HB.pipeline;
    },

    get: function (name) {
      return registry[name];
    },

    list: function () {
      return Object.keys(registry);
    },

    /** 跑一次解码流水线。 */
    run: function () {
      /*HB:NATIVE*/
      var plain = registry.decoder(SEED_2);
      return _consume(plain);
    }
  };

  HB.pipeline.register('decoder', function (token) {
    return decode(token);
  });

  var gate2 = {
    check: function (p) {
      return p === decode(SEED_2);
    }
  };
  if (HB._debugMode) {
    gate2.expected = function () {
      return decode(SEED_2);
    };
  }
  HB._register(2, gate2);
})(typeof globalThis !== 'undefined' ? globalThis : this);
