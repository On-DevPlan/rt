"""config_builder：base 模板 / 订阅解析 / 安全合并。"""
import pytest
import yaml

from rt_backend.proxy.config_builder import (
    SubscriptionInvalidError,
    build_config,
    parse_subscription,
    render_base_yaml,
)


def _load(text):
    return yaml.safe_load(text)


def test_base_yaml_forced_keys():
    cfg = _load(render_base_yaml())
    assert cfg["mixed-port"] == 7890
    assert cfg["bind-address"] == "127.0.0.1"
    assert cfg["allow-lan"] is False
    assert cfg["mode"] == "rule"
    assert cfg["external-controller"] == "127.0.0.1:9090"
    assert cfg["tun"]["enable"] is False
    assert cfg["dns"]["enable"] is True
    assert cfg["profile"]["store-selected"] is True


def test_stub_yaml_boots_empty():
    cfg = _load(render_base_yaml(stub=True))
    assert cfg["proxies"] == []
    assert cfg["rules"] == ["MATCH,DIRECT"]
    # stub 同样不允许默认带 tun
    assert cfg["tun"]["enable"] is False


def test_parse_subscription_ok():
    sub = parse_subscription(
        yaml.safe_dump(
            {
                "proxies": [{"name": "hk-1", "type": "ss", "server": "1.2.3.4", "port": 443}],
                "proxy-groups": [{"name": "PROXY", "type": "select", "proxies": ["hk-1"]}],
                "rules": ["MATCH,PROXY"],
                "mixed-port": 9999,  # 应被忽略，不影响 parse
            }
        )
    )
    assert sub["proxies"][0]["name"] == "hk-1"


def test_parse_subscription_empty_proxies_rejected():
    with pytest.raises(SubscriptionInvalidError):
        parse_subscription(yaml.safe_dump({"proxies": []}))


def test_parse_subscription_providers_only_ok():
    sub = parse_subscription(
        yaml.safe_dump(
            {"proxy-providers": {"sub1": {"type": "http", "url": "https://x", "path": "./p.yaml"}}}
        )
    )
    assert "sub1" in sub["proxy-providers"]


def test_parse_subscription_raw_node_list_rejected():
    body = "vmess://eyJhZGQiOiAxLjIuMy40fQ==\ntrojan://pass@host:443#node"
    with pytest.raises(SubscriptionInvalidError, match="Clash"):
        parse_subscription(body)


def test_parse_subscription_base64_wrapped_node_list_rejected():
    import base64

    raw = "vless://uuid@1.2.3.4:443#n1\nhysteria2://pw@5.6.7.8:443#n2"
    with pytest.raises(SubscriptionInvalidError, match="Clash"):
        parse_subscription(base64.b64encode(raw.encode()).decode())


def test_parse_subscription_not_mapping_rejected():
    with pytest.raises(SubscriptionInvalidError):
        parse_subscription("just a plain string")


def test_build_config_drops_dangerous_keys():
    sub = yaml.safe_load(
        yaml.safe_dump(
            {
                "proxies": [{"name": "hk-1", "type": "ss", "server": "s", "port": 1}],
                "proxy-groups": [{"name": "PROXY", "type": "select", "proxies": ["hk-1"]}],
                "rules": ["DOMAIN-SUFFIX,example.com,PROXY", "MATCH,PROXY"],
                # 以下全部是必须被丢弃的危险键
                "tun": {"enable": True},
                "external-controller": "0.0.0.0:9999",
                "secret": "evil",
                "port": 1234,
                "mixed-port": 1234,
                "allow-lan": True,
                "iptables": True,
                "dns": {"enable": False},
            }
        )
    )
    cfg = build_config(sub)
    assert cfg["mixed-port"] == 7890
    assert cfg["external-controller"] == "127.0.0.1:9090"
    assert cfg["tun"]["enable"] is False
    assert cfg["allow-lan"] is False
    assert "secret" not in cfg
    assert "iptables" not in cfg
    assert cfg["dns"]["enable"] is True
    # 流量键存活
    assert cfg["proxies"][0]["name"] == "hk-1"
    assert cfg["rules"][0] == "DOMAIN-SUFFIX,example.com,PROXY"


def test_build_config_synthesizes_missing_rules():
    sub = yaml.safe_load(
        yaml.safe_dump(
            {
                "proxies": [{"name": "hk-1", "type": "ss", "server": "s", "port": 1}],
                "proxy-groups": [{"name": "🚀 节点选择", "type": "select", "proxies": ["hk-1"]}],
            }
        )
    )
    cfg = build_config(sub)
    assert cfg["rules"] == ["MATCH,🚀 节点选择"]


def test_build_config_synthesizes_to_first_proxy_when_no_groups():
    sub = yaml.safe_load(
        yaml.safe_dump({"proxies": [{"name": "us-1", "type": "ss", "server": "s", "port": 1}]})
    )
    cfg = build_config(sub)
    assert cfg["rules"] == ["MATCH,us-1"]


def test_build_config_no_nodes_at_all_rejected():
    sub = yaml.safe_load(yaml.safe_dump({"proxy-providers": {"p": {"type": "http", "url": "x"}}}))
    with pytest.raises(SubscriptionInvalidError):
        build_config(sub)
