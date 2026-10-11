"""ProxySettingsStore：roundtrip / 缺文件 / 坏 JSON / 原子写无残留。"""
from rt_backend.proxy.store import DEFAULT_ALLOW_MODULES, ProxySettings, ProxySettingsStore


def test_roundtrip(tmp_path):
    store = ProxySettingsStore(tmp_path)
    s = ProxySettings(
        subscription_url="https://panel.example.com/sub?token=x",
        enabled=True,
        allow_modules=["skill_seekers", "anime_season"],
        updated_at="2026-10-11T00:00:00",
    )
    store.save(s)
    loaded = store.load()
    assert loaded == s


def test_missing_file_returns_defaults(tmp_path):
    store = ProxySettingsStore(tmp_path / "fresh")
    s = store.load()
    assert s.subscription_url is None
    assert s.enabled is False
    assert s.allow_modules == DEFAULT_ALLOW_MODULES


def test_corrupt_json_returns_defaults(tmp_path):
    store = ProxySettingsStore(tmp_path)
    (tmp_path / "proxy_settings.json").write_text("{not json", encoding="utf-8")
    s = store.load()
    assert s.subscription_url is None
    assert s.allow_modules == DEFAULT_ALLOW_MODULES


def test_non_dict_json_returns_defaults(tmp_path):
    store = ProxySettingsStore(tmp_path)
    (tmp_path / "proxy_settings.json").write_text('["list"]', encoding="utf-8")
    assert store.load().enabled is False


def test_save_atomic_no_tmp_left(tmp_path):
    store = ProxySettingsStore(tmp_path)
    store.save(ProxySettings(subscription_url="https://x", enabled=False))
    assert (tmp_path / "proxy_settings.json").exists()
    assert not (tmp_path / "proxy_settings.json.tmp").exists()


def test_config_path_under_root(tmp_path):
    store = ProxySettingsStore(tmp_path)
    assert store.config_path == tmp_path / "mihomo" / "config.yaml"


def test_empty_allow_modules_falls_back_to_default(tmp_path):
    store = ProxySettingsStore(tmp_path)
    store.save(ProxySettings(allow_modules=[]))
    assert store.load().allow_modules == DEFAULT_ALLOW_MODULES
