"""当班身份、班次与交接班状态。

骨架阶段还没有接入统一登录：前端在顶栏选择当班人员后，每个请求通过
X-Operator-Id 头带上身份，服务端据此判断“这单是谁理的、现在是不是当班的
值班负责人”。换成真实登录后，只需要把 require_operator 改为解析令牌即可。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from fastapi import Header, HTTPException

ROLE_TALLY = "tally"
ROLE_LEAD = "lead"
ROLE_VIEWER = "viewer"
ROLE_LABELS = {
    ROLE_TALLY: "理货人员",
    ROLE_LEAD: "值班负责人",
    ROLE_VIEWER: "只读查看",
}


@dataclass(frozen=True)
class Operator:
    id: str
    name: str
    role: str

    @property
    def role_label(self) -> str:
        return ROLE_LABELS.get(self.role, self.role)


# 演示用人员目录：理货人员、值班负责人与一个只读账号。
OPERATORS: list[Operator] = [
    Operator("tally-zhang", "张理货", ROLE_TALLY),
    Operator("tally-li", "李理货", ROLE_TALLY),
    Operator("tally-wang", "王理货", ROLE_TALLY),
    Operator("lead-zhao", "赵班长", ROLE_LEAD),
    Operator("lead-qian", "钱班长", ROLE_LEAD),
    Operator("viewer", "来访查看", ROLE_VIEWER),
]
OPERATOR_MAP = {operator.id: operator for operator in OPERATORS}

# 班次按交接班顺序轮转：白班 → 夜班 → 白班……
SHIFT_SEQUENCE: list[dict[str, Any]] = [
    {"label": "白班 08:00-20:00", "lead_id": "lead-zhao", "clerk_ids": ["tally-zhang", "tally-li"]},
    {"label": "夜班 20:00-08:00", "lead_id": "lead-qian", "clerk_ids": ["tally-wang"]},
]


def now_text() -> str:
    """统一的留痕时间格式，退回、提交都用它。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def find_operator(operator_id: str | None) -> Operator | None:
    if not operator_id:
        return None
    return OPERATOR_MAP.get(operator_id)


def require_operator(x_operator_id: str | None = Header(default=None)) -> Operator:
    """接口依赖：解析当班人员身份，缺失或无法识别时拒绝并说明原因。"""
    if not x_operator_id:
        raise HTTPException(status_code=401, detail="缺少当班人员身份（X-Operator-Id），请先在顶栏选择当班人员")
    operator = find_operator(x_operator_id)
    if operator is None:
        raise HTTPException(status_code=401, detail=f"未知的当班人员：{x_operator_id}，请重新选择身份")
    return operator


class ShiftBoard:
    """当前班次与交接班记录。只维护“现在是哪一班”，不搬移任何理货单。

    已提交的单据自带提交班次，新班次自然可见；未提交的单据绑定归属人，
    跟着人走，与班次状态互不影响。
    """

    def __init__(self) -> None:
        self._index = 0
        self.handover_history: list[dict[str, Any]] = []

    @property
    def index(self) -> int:
        return self._index

    def current(self) -> dict[str, Any]:
        return self._describe(self._index)

    def next(self) -> dict[str, Any]:
        return self._describe((self._index + 1) % len(SHIFT_SEQUENCE))

    def handover(self, operator: Operator) -> dict[str, Any]:
        current = self.current()
        record = {
            "from_shift": current["label"],
            "to_shift": self.next()["label"],
            "by_id": operator.id,
            "by_name": operator.name,
            "handed_at": now_text(),
        }
        self._index = (self._index + 1) % len(SHIFT_SEQUENCE)
        self.handover_history.append(record)
        return record

    def roster_shift_label(self, operator_id: str) -> str:
        """标注某名理货人员当前排在哪一班：用于体现“未提交的单跟着人走”。"""
        for index, shift in enumerate(SHIFT_SEQUENCE):
            if operator_id == shift["lead_id"] or operator_id in shift["clerk_ids"]:
                state = "当班" if index == self._index else "未当班"
                return f"{shift['label']}（{state}）"
        return "未排班"

    @staticmethod
    def _describe(index: int) -> dict[str, Any]:
        shift = SHIFT_SEQUENCE[index]
        lead = find_operator(shift["lead_id"])
        clerks = [operator for operator in (find_operator(cid) for cid in shift["clerk_ids"]) if operator]
        return {
            "index": index,
            "label": shift["label"],
            "lead_id": shift["lead_id"],
            "lead_name": lead.name if lead else "",
            "clerks": [{"id": clerk.id, "name": clerk.name, "role": clerk.role} for clerk in clerks],
        }


board = ShiftBoard()
