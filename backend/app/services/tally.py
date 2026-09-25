"""理货作业业务规则：归属控制、状态流转、提交锁定与负责人退回都收在这里。

归属口径：
- 理货单登记即归属当前理货人员（"理货人员"字段同时作为归属人）；
- 未提交（待理货/理货中）时，只有归属人本人能改动；其他人只读；
- "提交复核"后单据锁定，任何人不能直接改，必须由值班负责人"退回整改"；
- 退回会记录时间、理由、退回人，并把状态打回"理货中"，原有录入原样保留；
- 归属跟人不跟班：交接班不改归属，未提交的单跟着理货人员走。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.identity import Actor
from app.store import store

MODULE = "tally"
REQUIRED_FIELDS = ["理货单号", "关联航次", "理货方式"]
# 归属人在未提交阶段可维护的录入字段（理货方式选择与数据录入都在其中）
EDITABLE_FIELDS = ["关联航次", "理货方式", "理货箱量", "残损箱数"]
TALLY_METHODS = ["船边理货", "堆场理货", "舱内理货", "闸口理货"]

STATUS_ORDER = ["待理货", "理货中", "待复核", "已完成"]
# 已提交（锁定）状态：提交复核之后即进入只读冻结阶段
SUBMITTED_STATUSES = ["待复核", "已完成"]

# 归属人可执行的常规动作
ACTION_RULES = {"开始理货": "理货中", "提交复核": "待复核"}
# 值班负责人专属动作
SUPERVISOR_ACTION_RULES = {"确认完成": "已完成", "退回整改": "理货中"}


class TallyService:
    def list_entries(
        self,
        actor: Actor,
        *,
        keyword: str | None = None,
        status: str | None = None,
        owner: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("理货单号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if owner:
            rows = [row for row in rows if row.get("理货人员") == owner]
        total = len(rows)
        start = max(page - 1, 0) * size
        page_rows = rows[start:start + size]
        # 列表里每个人都能看，但要标明归属、锁定状态以及当前身份能否操作
        return [self._with_access(row, actor) for row in page_rows], total

    def get_entry(self, entry_id: int, actor: Actor) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None
        return self._with_access(entry, actor)

    def create_entry(
        self, values: dict[str, Any], actor: Actor
    ) -> tuple[dict[str, Any] | None, list[str], str | None]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing, None
        method = str(values.get("理货方式") or "").strip()
        if method not in TALLY_METHODS:
            return None, [], f"理货方式「{method}」不在可选范围：{'、'.join(TALLY_METHODS)}"

        rows = store.rows(MODULE)
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in REQUIRED_FIELDS:
            entry[field] = str(values.get(field) or "").strip()
        # 箱量/残损为选填录入项，给了就存
        for field in ("理货箱量", "残损箱数"):
            if str(values.get(field) or "").strip():
                entry[field] = str(values.get(field)).strip()
        # 归属即当前理货人员：单据跟着人走，不能登记给别人
        entry["理货人员"] = actor.name
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        entry["submitted"] = False
        entry["submitted_at"] = None
        entry["return_history"] = []
        rows.append(entry)
        return self._with_access(entry, actor), [], None

    def update_entry(
        self, entry_id: int, values: dict[str, Any], actor: Actor
    ) -> tuple[dict[str, Any] | None, str]:
        """未提交阶段归属人维护录入字段；越权或已提交一律拒绝并说明原因。"""
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"理货单 {entry_id} 不存在或已归档"

        denied = self._deny_mutation(entry, actor)
        if denied:
            return None, denied

        method = values.get("理货方式")
        if method is not None and str(method).strip() and str(method).strip() not in TALLY_METHODS:
            return None, f"理货方式「{method}」不在可选范围：{'、'.join(TALLY_METHODS)}"

        changed: list[str] = []
        for field in EDITABLE_FIELDS:
            if field not in values:
                continue
            value = str(values.get(field) or "").strip()
            if value != str(entry.get(field, "") or ""):
                entry[field] = value
                changed.append(field)
        return self._with_access(entry, actor), (
            f"理货单 {entry.get('理货单号')} 已更新（{ '、'.join(changed) }）"
            if changed
            else "内容没有变化"
        )

    def run_action(
        self, entry_id: int, action: str, actor: Actor, reason: str | None = None
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"理货单 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES and action not in SUPERVISOR_ACTION_RULES:
            return None, f"动作「{action}」不属于理货作业可执行范围"

        owner = str(entry.get("理货人员") or "")
        status = str(entry.get("status") or "")

        if action in ACTION_RULES:
            # 常规动作只有归属人本人能执行
            if entry.get("submitted"):
                return None, (
                    f"理货单已提交复核处于锁定状态，不能{action}；"
                    f"如需修改请请值班负责人退回整改"
                )
            if actor.name != owner:
                return None, (
                    f"越权操作被拒绝：理货单 {entry.get('理货单号')} 归属理货人员「{owner}」，"
                    f"当前操作人「{actor.name}」只能查看，不能{action}"
                )
            target = ACTION_RULES[action]
            expected = STATUS_ORDER[STATUS_ORDER.index(target) - 1]
            if status != expected:
                return None, f"当前状态「{status}」不能{action}，请先完成「{expected}」阶段"

        if action in SUPERVISOR_ACTION_RULES:
            if not actor.is_supervisor:
                return None, (
                    f"越权操作被拒绝：{action}仅限值班负责人执行，"
                    f"「{actor.name}」当前身份是{actor.role_label}"
                )
            target = SUPERVISOR_ACTION_RULES[action]
            if action == "确认完成":
                if status != "待复核":
                    return None, f"当前状态「{status}」不能确认完成，仅待复核的单据可确认"
            if action == "退回整改":
                if status not in SUBMITTED_STATUSES:
                    return None, "只有已提交（待复核/已完成）的单据才需要退回"
                reason_text = (reason or "").strip()
                if not reason_text:
                    return None, "退回必须填写退回理由，便于归属理货人员核对整改"
                record = {
                    "time": _now_text(),
                    "reason": reason_text,
                    "supervisor": actor.name,
                    "from_status": status,
                }
                entry.setdefault("return_history", []).append(record)

        entry["status"] = target
        # 提交后进入锁定；退回后解锁，归属人可继续修改并重新提交
        submitted = target in SUBMITTED_STATUSES
        entry["submitted"] = submitted
        entry["pending"] = target != STATUS_ORDER[-1]
        if action == "提交复核":
            entry["submitted_at"] = _now_text()
        if action == "退回整改":
            entry["submitted"] = False
            entry["submitted_at"] = None
        entry["abnormal"] = action == "退回整改"
        return self._with_access(entry, actor), self._success_message(action, entry, reason)

    # ---- 内部规则 ----

    def _deny_mutation(self, entry: dict[str, Any], actor: Actor) -> str | None:
        """判定当前操作人能否改动单据，不能改时返回可读原因。"""
        owner = str(entry.get("理货人员") or "")
        if entry.get("submitted"):
            if actor.is_supervisor:
                return (
                    f"理货单已提交（{entry.get('status')}）已锁定，负责人也不能直接改；"
                    f"请先执行「退回整改」并填写理由"
                )
            return (
                f"理货单已提交（{entry.get('status')}）已锁定，不能直接修改；"
                f"需由值班负责人退回后，归属人「{owner}」才能改动"
            )
        if actor.name != owner:
            return (
                f"越权改动被拒绝：理货单 {entry.get('理货单号')} 归属「{owner}」，"
                f"当前操作人「{actor.name}」只有查看权限"
            )
        return None

    def _with_access(self, entry: dict[str, Any], actor: Actor) -> dict[str, Any]:
        """给只读视图附上当前操作人的权限标记，供前端控制显隐（后端仍会独立校验）。"""
        view = dict(entry)
        owner = str(entry.get("理货人员") or "")
        locked = bool(entry.get("submitted"))
        is_owner = actor.name == owner
        view["owner_name"] = owner
        view["is_owner"] = is_owner
        view["locked"] = locked
        view["can_edit"] = is_owner and not locked
        view["can_submit"] = is_owner and not locked
        view["can_return"] = actor.is_supervisor and locked
        view["can_confirm"] = actor.is_supervisor and entry.get("status") == "待复核"
        view["actor"] = str(actor)
        return view

    @staticmethod
    def _success_message(action: str, entry: dict[str, Any], reason: str | None) -> str:
        if action == "退回整改":
            return (
                f"理货单 {entry.get('理货单号')} 已退回归属人「{entry.get('理货人员')}」整改，"
                f"原录入保留，退回时间与理由已记录"
            )
        return f"理货单已{action}"


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
