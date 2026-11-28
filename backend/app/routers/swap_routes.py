"""参展商换位交接路由：进场状态、物料接收、回执发放与原编号查询。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.services import swap

swap_router = APIRouter(prefix="/api/swap", tags=["参展商换位交接"])


@swap_router.get("/handovers")
def list_handovers() -> dict:
    """全部换位交接单。"""
    rows = swap._handover_rows()
    return {"items": rows, "total": len(rows)}


@swap_router.get("/handover/{handover_id}/status")
def handover_status(handover_id: int) -> dict:
    """交接单进场状态：甲乙双方可进场性、两箱物料接收人、阻塞冲突。"""
    result = swap.entry_status(handover_id)
    if not result["ok"]:
        raise HTTPException(status_code=404, detail=result["reason"])
    return result


@swap_router.post("/handover/{handover_id}/receipt")
def generate_receipt(handover_id: int, operator: str = "值班负责人") -> dict:
    """按展位与待交物料给接手企业发放进场回执；重复提交不会多发。"""
    result = swap.issue_entry_receipt(handover_id, operator=operator)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result.get("reason", "发放失败"))
    return result


@swap_router.post("/handover/{handover_id}/material/{material_id}/release")
def release_material(
    handover_id: int,
    material_id: int,
    receiver_enterprise: str,
    receiver_name: str,
) -> dict:
    """清点物料并登记接收人。"""
    result = swap.release_materials(
        handover_id, material_id,
        receiver_enterprise=receiver_enterprise,
        receiver_name=receiver_name,
    )
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["reason"])
    return result


@swap_router.post("/handover/{handover_id}/settle")
def settle(handover_id: int) -> dict:
    """交方结算归档。"""
    result = swap.settle_handover(handover_id)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["reason"])
    return result


@swap_router.get("/records/{enterprise_no}")
def query_by_no(enterprise_no: str) -> dict:
    """已结算原企业用原编号查询交出记录与接位回执。"""
    result = swap.record_by_no(enterprise_no)
    if not result["ok"]:
        raise HTTPException(status_code=404, detail=f"编号 {enterprise_no} 没有交接记录")
    return result


@swap_router.get("/receipt-audit")
def receipt_audit() -> dict:
    """核对同一展位同一时段是否多发进场回执。"""
    return swap.duplicate_receipt_audit()
