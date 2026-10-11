"""代理设置 JSON 持久化（原子写）。缺文件 / 坏 JSON 一律回落默认值，不抛。"""
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

# 默认白名单：文档站抓取是被代理的核心场景
DEFAULT_ALLOW_MODULES = ["skill_seekers"]


@dataclass
class ProxySettings:
    subscription_url: Optional[str] = None
    enabled: bool = False
    allow_modules: list[str] = field(default_factory=lambda: list(DEFAULT_ALLOW_MODULES))
    updated_at: Optional[str] = None


class ProxySettingsStore:
    def __init__(self, root: str | os.PathLike) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)
        self._file = self._root / "proxy_settings.json"

    @property
    def config_path(self) -> Path:
        return self._root / "mihomo" / "config.yaml"

    def load(self) -> ProxySettings:
        try:
            raw = json.loads(self._file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return ProxySettings()
        if not isinstance(raw, dict):
            return ProxySettings()
        allow = raw.get("allow_modules")
        return ProxySettings(
            subscription_url=raw.get("subscription_url") or None,
            enabled=bool(raw.get("enabled", False)),
            allow_modules=list(allow) if isinstance(allow, list) and allow else list(DEFAULT_ALLOW_MODULES),
            updated_at=raw.get("updated_at") or None,
        )

    def save(self, settings: ProxySettings) -> None:
        tmp = self._file.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(asdict(settings), ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self._file)
