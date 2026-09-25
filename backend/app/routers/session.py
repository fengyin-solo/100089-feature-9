"""当班身份与交接班接口：人员目录、当前班次、交接班与交接记录。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.identity import OPERATORS, ROLE_LEAD, Operator, board, require_operator

router = APIRouter(prefix="/api/session", tags=["当班身份"])


def _operator_brief(operator: Operator) -> dict[str, str]:
    return {"id": operator.id, "name": operator.name, "role": operator.role, "role_label": operator.role_label}


@router.get("")
def session_info() -> dict:
    """人员目录、当前班次、下一班次与交接记录，供顶栏与理货页展示。"""
    return {
        "operators": [_operator_brief(operator) for operator in OPERATORS],
        "current_shift": board.current(),
        "next_shift": board.next(),
        "handover_history": board.handover_history,
    }


@router.post("/handover")
def handover(operator: Operator = Depends(require_operator)) -> dict:
    """交接班：只有当前班次的值班负责人能执行，其他班次负责人也不行。"""
    current = board.current()
    if operator.role != ROLE_LEAD:
        raise HTTPException(status_code=403, detail=f"{operator.name} 不是值班负责人，无权执行交接班")
    if operator.id != current["lead_id"]:
        raise HTTPException(
            status_code=403,
            detail=f"当前班次（{current['label']}）的值班负责人是 {current['lead_name']}，{operator.name} 无权执行交接班",
        )
    record = board.handover(operator)
    return {
        "ok": True,
        "message": f"已交接至{record['to_shift']}，值班负责人：{board.current()['lead_name']}",
        "record": record,
        "current_shift": board.current(),
        "next_shift": board.next(),
    }
