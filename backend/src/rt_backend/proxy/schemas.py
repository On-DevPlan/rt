"""代理模块 pydantic 模型。"""
from typing import Optional

from pydantic import BaseModel, Field


class SubscriptionRequest(BaseModel):
    url: str = Field(min_length=8, description="Clash/Clash.Meta 格式的订阅链接")


class ToggleRequest(BaseModel):
    enabled: bool


class AllowlistRequest(BaseModel):
    modules: list[str] = Field(description="允许走代理的模块名列表（空列表 = 全部直连）")


class SubscriptionResponse(BaseModel):
    ok: bool = True
    proxies: Optional[int] = Field(default=None, description="节点数")
    groups: Optional[int] = Field(default=None, description="策略组数")
    rules: Optional[int] = Field(default=None, description="规则条数")
    enabled: bool = Field(description="当前开关状态（本操作不改变它）")
    mihomo_reloaded: bool
    mihomo_version: Optional[str] = None
    updated_at: Optional[str] = None


class ToggleResponse(BaseModel):
    enabled: bool
    effective: bool = Field(description="enabled 且 mihomo 存活且代理 client 已就绪")
    proxy_url: Optional[str] = None
    mihomo_version: Optional[str] = None


class AllowlistResponse(BaseModel):
    modules: list[str]
    enabled: bool


class MihomoInfo(BaseModel):
    running: bool
    version: Optional[str] = None
    proxies: Optional[int] = None
    groups: Optional[int] = None


class EgressInfo(BaseModel):
    direct_ip: Optional[str] = None
    proxied_ip: Optional[str] = None


class ProxyStatusResponse(BaseModel):
    subscription_url: Optional[str]
    subscription_set: bool
    enabled: bool
    effective: bool = Field(description="enabled 且 mihomo 存活且代理 client 已就绪")
    proxy_url: Optional[str] = Field(default=None, description="代理 client 当前指向；None=未启用")
    allow_modules: list[str]
    mihomo: MihomoInfo
    config_present: bool
    config_path: str
    updated_at: Optional[str] = None
    egress: Optional[EgressInfo] = Field(default=None, description="check_ip=true 时返回")
