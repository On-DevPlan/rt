"""mihomo 配置生成与订阅合并（纯函数，无网络）。

安全边界：合并时我方 base 键全胜，订阅内容只允许携带 7 个流量键
（proxies / proxy-groups / proxy-providers / rule-providers / rules /
sub-rules / script）。订阅里的 tun / external-controller / secret /
port* / iptables / dns 一律丢弃——坏订阅不得在容器内开 TUN、改控制面、开端口。
"""
import base64
import re
from pathlib import Path
from typing import Any, Optional

import yaml


class SubscriptionInvalidError(ValueError):
    """订阅内容不是可用的 Clash 配置。"""


# 我方强制覆盖的键（订阅里出现同名键一律忽略）
BASE_OVERRIDE_KEYS = (
    "mixed-port", "port", "socks-port", "redir-port", "tproxy-port",
    "bind-address", "allow-lan", "mode", "log-level", "ipv6",
    "external-controller", "external-ui", "secret",
    "tun", "dns", "profile", "iptables", "ebpf",
)

# 订阅只允许携带的流量键
SUB_KEYS = (
    "proxies", "proxy-groups", "proxy-providers",
    "rule-providers", "rules", "sub-rules", "script",
)

# base64 嗅探：命中说明订阅返回的是原始分享链接列表，不是 Clash YAML
_NODE_LINE_RE = re.compile(r"^(vmess|ss|ssr|trojan|vless|hysteria2?|tuic)://", re.MULTILINE)


def _base_dict(*, mixed_port: int = 7890, controller: str = "127.0.0.1:9090") -> dict[str, Any]:
    return {
        "mixed-port": mixed_port,
        "bind-address": "127.0.0.1",
        "allow-lan": False,
        "mode": "rule",
        "log-level": "info",
        "ipv6": False,
        "external-controller": controller,
        "tun": {"enable": False},
        "dns": {
            "enable": True,
            "listen": "127.0.0.1:1053",
            "ipv6": False,
            "enhanced-mode": "fake-ip",
            "fake-ip-range": "198.18.0.1/16",
            "fake-ip-filter": ["*.lan", "*.local", "+.local"],
            "default-nameserver": ["223.5.5.5", "119.29.29.29"],
            "nameserver": ["https://223.5.5.5/dns-query", "https://doh.pub/dns-query"],
        },
        "profile": {"store-selected": True},
    }


def to_yaml(cfg: dict[str, Any]) -> str:
    return yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False)


def render_base_yaml(
    *, mixed_port: int = 7890, controller: str = "127.0.0.1:9090", stub: bool = False
) -> str:
    """基础模板；stub=True 追加空 proxies + MATCH,DIRECT，让 mihomo 无订阅也能空跑。"""
    cfg = _base_dict(mixed_port=mixed_port, controller=controller)
    if stub:
        cfg["proxies"] = []
        cfg["rules"] = ["MATCH,DIRECT"]
    return to_yaml(cfg)


def write_base_yaml(path: str, **kw: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(render_base_yaml(**kw), encoding="utf-8")


def _sniff_node_list(text: str) -> bool:
    """探测 base64 包装的原始节点列表（vmess://... 每行一条）。"""
    stripped = text.strip()
    if _NODE_LINE_RE.search(stripped):
        return True
    try:
        decoded = base64.b64decode(stripped + "=" * (-len(stripped) % 4), validate=True)
        return _NODE_LINE_RE.search(decoded.decode("utf-8", errors="ignore")) is not None
    except Exception:
        return False


def parse_subscription(text: str) -> dict[str, Any]:
    """解析订阅响应体为 Clash 配置 dict；不合法抛 SubscriptionInvalidError。"""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        if _sniff_node_list(text):
            raise SubscriptionInvalidError(
                "订阅返回了原始节点分享链接列表，不是 Clash 配置——请使用 Clash/Clash.Meta 格式的订阅链接"
            ) from e
        raise SubscriptionInvalidError(f"订阅内容不是有效的 YAML：{e}") from e

    if not isinstance(data, dict):
        if _sniff_node_list(text):
            raise SubscriptionInvalidError(
                "订阅返回了原始节点分享链接列表，不是 Clash 配置——请使用 Clash/Clash.Meta 格式的订阅链接"
            )
        raise SubscriptionInvalidError("订阅内容不是有效的 Clash 配置（顶层必须是键值映射）")

    proxies = data.get("proxies")
    providers = data.get("proxy-providers")
    proxies_ok = isinstance(proxies, list) and len(proxies) > 0
    providers_ok = isinstance(providers, dict) and len(providers) > 0
    if not (proxies_ok or providers_ok):
        raise SubscriptionInvalidError("订阅配置里没有可用节点（proxies/proxy-providers 均为空）")
    if proxies_ok and not all(isinstance(p, dict) and p.get("name") for p in proxies):
        raise SubscriptionInvalidError("订阅 proxies 列表存在缺少 name 字段的节点")
    return data


def build_config(
    sub: dict[str, Any], *, mixed_port: int = 7890, controller: str = "127.0.0.1:9090"
) -> dict[str, Any]:
    """base 键全胜 + 订阅 7 个流量键，缺 rules 时合成 MATCH 到首个组/节点。"""
    cfg = _base_dict(mixed_port=mixed_port, controller=controller)
    for key in SUB_KEYS:
        value = sub.get(key)
        if value:  # 空列表/空 dict 不搬运
            cfg[key] = value

    if not cfg.get("rules"):
        first_group: Optional[str] = None
        groups = cfg.get("proxy-groups") or []
        if isinstance(groups, list) and groups and isinstance(groups[0], dict):
            first_group = groups[0].get("name")
        if not first_group:
            proxies = cfg.get("proxies") or []
            if isinstance(proxies, list) and proxies and isinstance(proxies[0], dict):
                first_group = proxies[0].get("name")
        if not first_group:
            raise SubscriptionInvalidError("订阅里既无 proxy-groups 也无 proxies，无法合成默认规则")
        cfg["rules"] = [f"MATCH,{first_group}"]
    return cfg
