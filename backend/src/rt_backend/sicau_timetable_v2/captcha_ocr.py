"""Captcha recognition via a GLM vision model (智谱 BigModel API).

The school's captcha (noisy 4-digit PNG) defeats ddddocr — GLM-4.6V-Flash
reads it far more reliably. Falls back to ddddocr if the API errors, so a
network hiccup at BigModel doesn't take the whole login down.
"""
import base64
import logging
import re

from openai import OpenAI

logger = logging.getLogger(__name__)

# Filled from Settings; None → ddddocr only.
_api_key: str | None = None
_client: OpenAI | None = None

MODEL = "glm-4.6v-flash"

_PROMPT = (
    "识别图片中的验证码。验证码恰好是4个数字字符（0-9），只包含数字，"
    "绝对不包含任何字母。图中可能有噪点、星星和干扰线，请忽略干扰，仔细辨认数字。"
    "直接输出这4个数字，禁止输出字母、汉字、标点、空格或任何解释。"
)

_ddocr = None


def configure(api_key: str) -> None:
    global _api_key, _client
    _api_key = api_key
    _client = OpenAI(api_key=api_key, base_url="https://open.bigmodel.cn/api/paas/v4/")


def _get_ddocr():
    global _ddocr
    if _ddocr is None:
        import ddddocr
        _ddocr = ddddocr.DdddOcr(show_ad=False)
    return _ddocr


def read_captcha(png_bytes: bytes) -> str:
    """Return the OCR'd captcha text (ideally 4 digits). Never raises — on any
    failure returns the ddddocr reading (possibly wrong length)."""
    if _client is not None:
        try:
            b64 = base64.b64encode(png_bytes).decode("ascii")
            resp = _client.chat.completions.create(
                model=MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": _PROMPT},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{b64}"},
                            },
                        ],
                    }
                ],
                temperature=0.1,
                timeout=10,
            )
            text = (resp.choices[0].message.content or "").strip()
            # Model sometimes wraps in prose; extract the digit run.
            digits = re.sub(r"\D", "", text)  # strip letters/punct entirely
            if len(digits) == 4:
                logger.info("glm captcha read: %r (raw %r)", digits, text)
                return digits
            logger.warning("glm captcha read unparsable: %r", text)
        except Exception as e:
            logger.warning("glm captcha API failed (%r); falling back to ddddocr", e)
    return _get_ddocr().classification(png_bytes)