"""理货作业接口：归属到人的登记、修改、提交、退回与交接班口径。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.identity import Operator, find_operator, require_operator
from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.tally import TALLY_METHODS, TallyRuleError, TallyService

router = APIRouter(prefix="/api/tally", tags=["理货作业"])

service = TallyService()

STATUSES = ["待理货", "理货中", "待复核", "已完成"]


class TallyReturnPayload(BaseModel):
    """退回已提交理货单时必须给出理由，服务端留痕。"""

    reason: str = Field(default="", description="退回理由，不能为空")


def _raise_rule(error: TallyRuleError) -> None:
    raise HTTPException(status_code=403, detail=str(error))


def _resolve_viewer(operator_id: str | None) -> Operator | None:
    """列表/详情允许匿名查看，但带上身份时会标注“是不是我的单”。"""
    return find_operator(operator_id)


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按理货单号检索"),
    status: str | None = Query(default=None, description="待理货、理货中、待复核、已完成"),
    scope: str | None = Query(default=None, description="mine 我的 / draft 未提交 / submitted 已提交"),
    operator_id: str | None = Query(default=None, description="查看者身份，用于标注归属"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按理货单号、状态与归属范围过滤；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    viewer = _resolve_viewer(operator_id)
    items, total = service.list_entries(keyword=keyword, status=status, scope=scope, operator=viewer, page=page, size=size)
    return PageResult(items=[service.decorate(item, viewer) for item in items], total=total, page=page, size=size)


@router.get("/meta")
def tally_meta() -> dict[str, Any]:
    """理货方式候选项与状态序列：保持原有录入习惯，不在前端写死。"""
    return {"tally_methods": TALLY_METHODS, "statuses": STATUSES}


@router.get("/stats")
def tally_stats(operator_id: str | None = Query(default=None)) -> dict[str, int]:
    """页头统计：总量、我的未提交、已提交、被退回。"""
    return service.stats(_resolve_viewer(operator_id))


@router.get("/export")
def export_entries(operator_id: str | None = Query(default=None)) -> dict[str, Any]:
    """导出理货作业清单：返回当前全量数据；带上身份时同样标注归属。"""
    viewer = _resolve_viewer(operator_id)
    items, total = service.list_entries(operator=viewer, page=1, size=10000)
    return {"module": "tally", "total": total, "items": [service.decorate(item, viewer) for item in items]}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int, operator_id: str | None = Query(default=None)) -> dict:
    """读取单条理货单明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"理货单 {entry_id} 不存在或已归档")
    return service.decorate(entry, _resolve_viewer(operator_id))


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload, operator: Operator = Depends(require_operator)) -> ActionResult:
    """登记理货单：只有理货人员能登记，归属人就是登记人本人。"""
    try:
        entry, missing = service.create_entry(payload.values, operator)
    except TallyRuleError as error:
        _raise_rule(error)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="理货单已登记，归属人为当前理货人员", entry=entry)


@router.patch("/{entry_id}", response_model=dict)
def update_entry(entry_id: int, payload: EntryPayload, operator: Operator = Depends(require_operator)) -> dict:
    """修改理货单内容：仅归属人本人、且单据未提交时允许，越权会被拒绝并说明原因。"""
    try:
        entry, message = service.update_entry(entry_id, payload.values, operator)
    except TallyRuleError as error:
        _raise_rule(error)
    if entry is None:
        raise HTTPException(status_code=400, detail=message)
    return service.decorate(entry, operator)


@router.post("/{entry_id}/submit", response_model=ActionResult)
def submit_entry(entry_id: int, operator: Operator = Depends(require_operator)) -> ActionResult:
    """提交理货单：归属人本人操作，提交后内容锁定并留存提交版本。"""
    try:
        entry, message = service.submit(entry_id, operator)
    except TallyRuleError as error:
        _raise_rule(error)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=service.decorate(entry, operator))


@router.post("/{entry_id}/return", response_model=ActionResult)
def return_entry(
    entry_id: int,
    payload: TallyReturnPayload,
    operator: Operator = Depends(require_operator),
) -> ActionResult:
    """退回已提交的理货单：仅当前班次值班负责人可执行，退回时间与理由留痕。"""
    try:
        entry, message = service.return_entry(entry_id, payload.reason, operator)
    except TallyRuleError as error:
        _raise_rule(error)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=service.decorate(entry, operator))


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload, operator: Operator = Depends(require_operator)) -> ActionResult:
    """开始理货、提交复核、确认完成：动作按归属与班次负责人规则校验，不允许的会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    try:
        entry, message = service.run_action(entry_id, action, operator)
    except TallyRuleError as error:
        _raise_rule(error)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=service.decorate(entry, operator))
