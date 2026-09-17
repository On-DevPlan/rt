/*!
 * hb-gate-05 — 镜像
 *
 * 页面用它解码 /attest 的响应。
 *
 * 注意它只解前 16 位。这不是 bug——页面只关心那 16 位，
 * 后面的部分被它直接丢掉了。你在 Network 面板里看到的 ct 长度，
 * 和页面上显示出来的长度，对不上。
 *
 * 你可以 hook 这里，也可以拿着 K4 自己把整段解开。
 * 但朴素 hook（直接替换函数）会让下面的指纹检查发现你——第 3 关学过怎么绕。
 */
(function (root) {
  'use strict';

  var HB = root.HB;
  var MARK = 'HB:G5';
  var HEAD_LEN = 16;

  function intact(fn) {
    return Function.prototype.toString.call(fn).indexOf(MARK) !== -1;
  }

  var codec = {
    /** 页面只调这个：解前 16 位就够了。 */
    decodeHead: function (keyHex, ct) {
      /*HB:G5*/
      var plain = HB.crypto.decrypt(keyHex, ct);
      return plain.slice(0, HEAD_LEN);
    },

    /** 指纹自检。 */
    intact: function () {
      return intact(codec.decodeHead);
    },

    /** 被 hook 了就说一声，但不拦。 */
    audit: function () {
      if (!intact(codec.decodeHead)) {
        root.console.warn(
          '%c[hb] E_HOOK_DETECTED — decodeHead 的源码指纹变了。',
          'color:#a65131;font-weight:700'
        );
        return false;
      }
      return true;
    }
  };

  HB.gate5 = codec;
})(typeof globalThis !== 'undefined' ? globalThis : this);
