"""请求身份解析：演示阶段用请求头识别当前理货人员与角色。

生产环境应替换为登录态 / Token 解析；这里保持无外部依赖，方便前端切换身份联调。
权限判定全部在服务层依据 Actor 完成，前端的显隐只是体验优化，不能替代后端校验。
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import unquote

from fastapi import Header

ROLE_TALLY = "tally"  # 理货人员
ROLE_SUPERVISOR = "supervisor"  # 值班负责人

ROLE_LABELS = {ROLE_TALLY: "理货人员", ROLE_SUPERVISOR: "值班负责人"}


def _decode_header(raw: str | None) -> str:
    """HTTP 头只能安全传 ASCII：前端对中文姓名做百分号编码，这里解码；
    同时兼容裸 UTF-8 字节被按 latin-1 解开的乱码（如部分客户端直接发中文）。"""
    text = (raw or "").strip()
    if not text:
        return ""
    text = unquote(text)
    try:
        # 正常解码后的中文无法再按 latin-1 编码，会抛异常并保留原文；
        # 乱码串全是 latin-1 字符，可还原成真正的 UTF-8 中文。
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


@dataclass(frozen=True)
class Actor:
    """一次请求对应的操作人。"""

    name: str
    role: str

    @property
    def is_supervisor(self) -> bool:
        return self.role == ROLE_SUPERVISOR

    @property
    def role_label(self) -> str:
        return ROLE_LABELS.get(self.role, "未知身份")

    def __str__(self) -> str:
        return f"{self.name}（{self.role_label}）"


def current_actor(
    x_operator: str | None = Header(default=None, alias="X-Operator"),
    x_operator_role: str | None = Header(default=None, alias="X-Operator-Role"),
) -> Actor:
    """从请求头解析当前操作人；缺省时给一个理货员身份，保证接口可直接联调。"""
    name = _decode_header(x_operator) or "演示理货员"
    role = _decode_header(x_operator_role)
    if role not in ROLE_LABELS:
        role = ROLE_TALLY
    return Actor(name=name, role=role)
