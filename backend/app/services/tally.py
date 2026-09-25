"""理货作业业务规则：归属到人、提交锁定、负责人退回与交接班口径都收在这里。

核心约定：
- 理货单按归属人（理货人员）划分，未提交前只有归属人本人能改；
- 提交后内容锁定并留存提交版本，任何人（含归属人）都不能直接改；
- 提交后要改，必须由当前班次的值班负责人退回，退回时记下时间与理由；
- 交接班只影响“当前班次”的归属标注：已提交的单新班次照常可见，
  未提交的单跟着归属人走，不随班次搬移。
"""
from __future__ import annotations

from typing import Any

from app.identity import ROLE_LEAD, ROLE_TALLY, Operator, board, now_text
from app.store import store

MODULE = "tally"
REQUIRED_FIELDS = ["理货单号", "关联航次", "理货方式"]
# 归属人可继续维护的字段：理货方式选择与录入保持原有习惯，不受归属规则影响。
EDITABLE_FIELDS = ["关联航次", "理货方式", "理货箱量", "残损箱数", "完成时间", "理货状态"]
TALLY_METHODS = ["船边理货", "舱口理货", "智能理货", "视频理货"]
STATUS_ORDER = ["待理货", "理货中", "待复核", "已完成"]
ACTION_RULES = {"开始理货": "理货中", "提交复核": "待复核", "确认完成": "已完成"}
NEGATIVE_ACTIONS: list[str] = []
# 列表/详情里随单返回的快照字段，便于前端直接展示提交版本与退回留痕。
SNAPSHOT_FIELDS = ["理货单号", "关联航次", "理货方式", "理货箱量", "残损箱数", "理货人员", "完成时间", "理货状态"]


class TallyRuleError(Exception):
    """归属或状态规则不满足时抛出，路由层统一转成 403。"""


class TallyService:
    # ---------- 查询 ----------

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        scope: str | None = None,
        operator: Operator | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("理货单号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if scope == "mine" and operator is not None:
            rows = [row for row in rows if row.get("owner_id") == operator.id]
        elif scope == "draft":
            rows = [row for row in rows if not row.get("submitted")]
        elif scope == "submitted":
            rows = [row for row in rows if row.get("submitted")]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def stats(self, operator: Operator | None = None) -> dict[str, int]:
        rows = store.rows(MODULE)
        mine = [row for row in rows if operator is not None and row.get("owner_id") == operator.id]
        return {
            "total": len(rows),
            "mine_unsubmitted": sum(1 for row in mine if not row.get("submitted")),
            "submitted": sum(1 for row in rows if row.get("submitted")),
            "returned": sum(1 for row in rows if row.get("return_records")),
        }

    def decorate(self, entry: dict[str, Any], operator: Operator | None) -> dict[str, Any]:
        """给单条记录补上“是不是我的、能不能改、归属人在哪一班”等展示信息。"""
        row = dict(entry)
        owner_id = str(row.get("owner_id") or "")
        is_owner = operator is not None and operator.id == owner_id
        row["mine"] = is_owner
        row["locked"] = bool(row.get("submitted"))
        row["owner_shift_label"] = board.roster_shift_label(owner_id) if owner_id else "未排班"
        row["can_edit"] = is_owner and not row.get("submitted")
        row["can_submit"] = row["can_edit"]
        row["can_return"] = (
            operator is not None
            and operator.role == ROLE_LEAD
            and operator.id == board.current()["lead_id"]
            and bool(row.get("submitted"))
        )
        return row

    # ---------- 登记与修改 ----------

    def create_entry(self, values: dict[str, Any], operator: Operator) -> tuple[dict[str, Any] | None, list[str]]:
        if operator.role != ROLE_TALLY:
            raise TallyRuleError(f"{operator.name}（{operator.role_label}）不是理货人员，不能登记理货单")
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        for field in EDITABLE_FIELDS:
            if field not in entry:
                entry[field] = values.get(field)
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        # 归属信息：谁登记的就是谁的单，理货人员列直接写归属人姓名。
        entry["owner_id"] = operator.id
        entry["owner_name"] = operator.name
        entry["理货人员"] = operator.name
        entry["submitted"] = False
        entry["submitted_at"] = None
        entry["submitted_by"] = None
        entry["submitted_shift"] = None
        entry["submitted_snapshot"] = None
        entry["return_records"] = []
        rows.append(entry)
        return entry, []

    def update_entry(
        self, entry_id: int, values: dict[str, Any], operator: Operator
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"理货单 {entry_id} 不存在或已归档"
        self._ensure_editable(entry, operator)
        changed = False
        for field in EDITABLE_FIELDS:
            if field in values:
                entry[field] = values.get(field)
                changed = True
        if not changed:
            return None, "没有可保存的字段：仅允许修改关联航次、理货方式、理货箱量、残损箱数、完成时间、理货状态"
        return entry, "理货单已保存"

    # ---------- 提交与退回 ----------

    def submit(self, entry_id: int, operator: Operator) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"理货单 {entry_id} 不存在或已归档"
        self._ensure_editable(entry, operator)
        entry["submitted"] = True
        entry["submitted_at"] = now_text()
        entry["submitted_by"] = operator.name
        entry["submitted_shift"] = board.current()["label"]
        entry["submitted_snapshot"] = {field: entry.get(field) for field in SNAPSHOT_FIELDS}
        # 与原有状态流转对齐：提交即进入待复核。
        entry["status"] = "待复核"
        entry["pending"] = True
        return entry, f"理货单已提交（{entry['submitted_shift']}），内容已锁定，如需修改请联系值班负责人退回"

    def return_entry(
        self, entry_id: int, reason: str, operator: Operator
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"理货单 {entry_id} 不存在或已归档"
        current = board.current()
        if operator.role != ROLE_LEAD:
            raise TallyRuleError(f"{operator.name}（{operator.role_label}）不是值班负责人，无权退回理货单")
        if operator.id != current["lead_id"]:
            raise TallyRuleError(
                f"当前班次（{current['label']}）的值班负责人是 {current['lead_name']}，{operator.name} 无权退回"
            )
        if not entry.get("submitted"):
            raise TallyRuleError("该理货单尚未提交，归属人可直接修改，无需退回")
        reason = reason.strip()
        if not reason:
            return None, "退回理由不能为空：退回已提交的理货单必须说明理由"
        record = {
            "returned_at": now_text(),
            "returned_by": operator.name,
            "shift": current["label"],
            "reason": reason,
        }
        entry.setdefault("return_records", []).append(record)
        entry["submitted"] = False
        entry["submitted_at"] = None
        entry["submitted_by"] = None
        entry["submitted_shift"] = None
        entry["submitted_snapshot"] = None
        # 退回后回到理货中，归属人继续按原方式录入。
        entry["status"] = "理货中"
        entry["pending"] = True
        return entry, f"理货单已退回给 {entry.get('owner_name', '归属人')}，退回理由：{reason}"

    # ---------- 原有动作流转（接入归属与锁定规则） ----------

    def run_action(self, entry_id: int, action: str, operator: Operator) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"理货单 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于理货作业可执行范围"
        if action == "开始理货":
            self._ensure_editable(entry, operator)
            if entry.get("status") != "待理货":
                return None, f"当前状态为「{entry.get('status')}」，只有待理货的单据才能开始理货"
        elif action == "提交复核":
            return self.submit(entry_id, operator)
        elif action == "确认完成":
            current = board.current()
            if operator.role != ROLE_LEAD or operator.id != current["lead_id"]:
                raise TallyRuleError(
                    f"确认完成需由当前班次（{current['label']}）值班负责人 {current['lead_name']} 复核，"
                    f"{operator.name}（{operator.role_label}）无权操作"
                )
            if not entry.get("submitted"):
                return None, "该理货单尚未提交，归属人提交后才能复核确认完成"
            if entry.get("status") == "已完成":
                return None, "该理货单已完成，无需重复确认"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"理货单已{action}"

    # ---------- 内部规则 ----------

    @staticmethod
    def _ensure_editable(entry: dict[str, Any], operator: Operator) -> None:
        """越权改动统一在这里拦下，并说明是谁的单、卡在哪条规则。"""
        if entry.get("submitted"):
            raise TallyRuleError(
                f"该理货单已由 {entry.get('submitted_by') or entry.get('owner_name')} 提交并锁定，"
                "任何人不能直接修改；如需修改，请联系当前班次的值班负责人退回"
            )
        owner_id = str(entry.get("owner_id") or "")
        if owner_id and operator.id != owner_id:
            raise TallyRuleError(
                f"该理货单归属 {entry.get('owner_name', '其他理货人员')}，"
                f"{operator.name}（{operator.role_label}）只能查看，不能修改"
            )
