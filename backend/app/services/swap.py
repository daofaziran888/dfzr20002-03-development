"""参展商换位交接：按展位与待交物料发放进场回执，保证同一展位同一时段
只有一家可进场企业，搬出前物料必须有接收人，已结算原企业仍可按原编号查交出记录。

三条领域铁律：
1. 一个（展位, 时段）只能有一张有效进场回执，重复提交不得多发。
2. 交接单下的待交物料全部清点并登记接收人，才允许把物料搬出展位。
3. 交方结算后仍用原登记编号（EXHI-xxxx）能查到自己的交出记录。
"""
from __future__ import annotations

import copy
from typing import Any

from app.store import store

# 同一展位同一时段互斥的交接状态：这些状态下回执仍然占用展位进场名额
OCCUPYING_STATUSES = {"有效", "待清点"}


def _handover_rows() -> list[dict[str, Any]]:
    return store.rows("swap_handover")


def _pending_rows() -> list[dict[str, Any]]:
    return store.rows("pending_material")


def _receipt_rows() -> list[dict[str, Any]]:
    return store.rows("entry_receipt")


def find_handover(handover_id: int) -> dict[str, Any] | None:
    for row in _handover_rows():
        if int(row.get("id", 0)) == handover_id:
            return row
    return None


def _receipts_for_slot(booth_no: str, slot: str) -> list[dict[str, Any]]:
    """按（展位, 时段）取占用中或历史有效回执。"""
    return [
        r for r in _receipt_rows()
        if str(r.get("展位编号", "")) == booth_no
        and str(r.get("交接时段", "")) == slot
        and str(r.get("status", "")) in OCCUPYING_STATUSES
    ]


def material_by_handover(handover_id: int) -> list[dict[str, Any]]:
    return [m for m in _pending_rows() if int(m.get("交接单", 0)) == handover_id]


def uncleared_materials(handover_id: int) -> list[dict[str, Any]]:
    """还没清点或还没登记接收人的物料——这些不许搬出展位。"""
    return [
        m for m in material_by_handover(handover_id)
        if str(m.get("清点状态", "")) != "已清点"
        or not str(m.get("接收人", "")).strip()
        or not str(m.get("接收企业", "")).strip()
    ]


def handover_blockers(handover_id: int) -> list[str]:
    """交接单提交进场回执前必须解除的阻塞项。"""
    handover = find_handover(handover_id)
    if handover is None:
        return [f"交接单 {handover_id} 不存在"]

    blockers: list[str] = []
    missing = uncleared_materials(handover_id)
    if missing:
        boxes = "、".join(str(m.get("箱号", "")) for m in missing)
        blockers.append(
            f"仍有 {len(missing)} 箱待交物料未清点或未登记接收人（{boxes}），不得搬出展位"
        )

    booth_no = str(handover.get("展位编号", ""))
    slot = str(handover.get("交接时段", ""))
    occupying = [
        r for r in _receipts_for_slot(booth_no, slot)
        if int(r.get("交接单", 0)) != handover_id
    ]
    if occupying:
        blockers.append(
            f"展位 {booth_no} 在时段 {slot} 已有可进场企业"
            f"（回执 {occupying[0].get('回执编号', '')} / {occupying[0].get('企业', '')}），同一时段只能一家进场"
        )
    return blockers


def entry_status(handover_id: int) -> dict[str, Any]:
    """查看交接单的进场状态：双方企业、物料接收、回执与阻塞冲突。"""
    handover = find_handover(handover_id)
    if handover is None:
        return {"ok": False, "reason": f"交接单 {handover_id} 不存在"}

    materials = material_by_handover(handover_id)
    receipts = [
        r for r in _receipt_rows() if int(r.get("交接单", 0)) == handover_id
    ]
    issued = [r for r in receipts if r.get("status") in OCCUPYING_STATUSES]
    material_view = [
        {
            "id": m.get("id"),
            "箱号": m.get("箱号", ""),
            "物料名称": m.get("物料名称", ""),
            "数量": m.get("数量"),
            "清点状态": m.get("清点状态", ""),
            "接收企业": m.get("接收企业", "") or "未登记",
            "接收人": m.get("接收人", "") or "未登记",
            "可搬出": str(m.get("清点状态", "")) == "已清点"
                      and bool(str(m.get("接收人", "")).strip()),
        }
        for m in materials
    ]
    blockers = handover_blockers(handover_id)

    # 同一张交接单上的两边诉求：仓库要交清材料，施工队要进场。
    warehouse_push = any(
        str(h.get("仓库催办", "")) == "是" for h in [handover]
    ) or len(uncleared_materials(handover_id)) > 0
    site_push = str(handover.get("接手申请进场", "")) == "是"

    return {
        "ok": True,
        "handover_id": handover_id,
        "booth_no": str(handover.get("展位编号", "")),
        "slot": str(handover.get("交接时段", "")),
        "outgoing": {
            "企业": handover.get("交出企业", ""),
            "企业编号": handover.get("交出编号", ""),
            "可进场": False,
            "说明": "交出企业已交出本时段，不可再申请进场",
        },
        "incoming": {
            "企业": handover.get("接手企业", ""),
            "企业编号": handover.get("接手编号", ""),
            "可进场": bool(issued),
            "申请进场": site_push,
        },
        "materials": material_view,
        "uncleared_count": len(uncleared_materials(handover_id)),
        "receipt": issued[0] if issued else None,
        "receipt_count": len(issued),
        "blockers": blockers,
        "can_issue": len(blockers) == 0 and not issued,
        "conflict": bool(blockers),
        "conflict_sides": {
            "仓库": "催交出方交清两箱材料" if warehouse_push else "无催办",
            "施工队": "催接手方进场" if site_push else "无催办",
            "结论": (
                "两份诉求在同一交接单上冲突：材料未清点前不能发放进场回执"
                if blockers else "无冲突，可按物料清点结果发放进场回执"
            ),
        },
        "receipt_materials": [
            {
                "id": m.get("id"),
                "箱号": m.get("箱号", ""),
                "接收企业": m.get("接收企业", "") or "未登记",
                "接收人": m.get("接收人", "") or "未登记",
            }
            for m in materials
            if int(m.get("id", 0)) in (issued[0].get("关联物料", []) if issued else [])
        ],
    }


def issue_entry_receipt(handover_id: int, operator: str = "值班负责人") -> dict[str, Any]:
    """按展位和待交物料给接手企业发放进场回执（幂等，不重复发放）。"""
    handover = find_handover(handover_id)
    if handover is None:
        return {"ok": False, "reason": f"交接单 {handover_id} 不存在"}

    existing = [
        r for r in _receipt_rows()
        if int(r.get("交接单", 0)) == handover_id
        and r.get("status") in OCCUPYING_STATUSES
    ]
    if existing:
        return {
            "ok": False,
            "reason": f"交接单 {handover_id} 已发放进场回执 {existing[0].get('回执编号', '')}，不重复发放",
            "receipt": existing[0],
            "blocked": True,
        }

    blockers = handover_blockers(handover_id)
    if blockers:
        return {
            "ok": False,
            "reason": "；".join(blockers),
            "blockers": blockers,
            "materials": [
                {"箱号": m.get("箱号"), "接收人": m.get("接收人") or "未登记"}
                for m in material_by_handover(handover_id)
            ],
            "blocked": True,
        }

    booth_no = str(handover.get("展位编号", ""))
    slot = str(handover.get("交接时段", ""))
    booth = store.find_booth(booth_no)
    if booth is None:
        return {"ok": False, "reason": f"展位 {booth_no} 不存在，不能发放进场回执"}
    if booth.get("status") != "已确认":
        return {"ok": False, "reason": f"展位 {booth_no} 尚未确认，不能发放进场回执"}

    margins = material_by_handover(handover_id)
    receipt_id = store.next_id("entry_receipt")
    receipt = {
        "id": receipt_id,
        "status": "有效",
        "pending": False,
        "abnormal": False,
        "回执编号": f"RCPT-{receipt_id:04d}",
        "交接单": handover_id,
        "展位编号": booth_no,
        "交接时段": slot,
        "企业": handover.get("接手企业", ""),
        "企业编号": handover.get("接手编号", ""),
        "发放时间": handover.get("交接时刻", ""),
        "关联物料": [m.get("id") for m in margins],        "登记编号": f"RCPT-{receipt_id:04d}",
        "负责人": operator,
        "生效版本": "v1.0",
        "备注说明": "按展位与待交物料发放，物料接收人已登记",
    }

    before = copy.deepcopy(handover)
    handover["status"] = "已确认"
    handover["pending"] = False
    handover["abnormal"] = False
    handover["交接状态"] = "已交接"
    _receipt_rows().append(receipt)

    store.event_log.record(
        module="swap_handover",
        entry_id=handover_id,
        action="发放进场回执",
        before=before,
        after=copy.deepcopy(handover),
        extra={
            "booth_no": booth_no,
            "slot": slot,
            "receipt_no": receipt["回执编号"],
            "receipt_id": receipt_id,
            "enterprise": receipt["企业"],
            "enterprise_no": receipt["企业编号"],
            "material_ids": receipt["关联物料"],
            "operator": operator,
        },
    )
    store.rebuild_indices()

    return {
        "ok": True,
        "reason": f"已向 {receipt['企业']} 发放进场回执 {receipt['回执编号']}",
        "receipt": receipt,
        "handover": handover,
        "materials": [
            {
                "箱号": m.get("箱号"),
                "物料名称": m.get("物料名称"),
                "接收人": m.get("接收人"),
                "接收企业": m.get("接收企业"),
            }
            for m in margins
        ],
        "entry_status": entry_status(handover_id),
    }


def release_materials(
    handover_id: int,
    material_id: int,
    receiver_enterprise: str,
    receiver_name: str,
) -> dict[str, Any]:
    """清点物料并登记接收人；两箱都登记完，物料才允许搬出展位。"""
    handover = find_handover(handover_id)
    if handover is None:
        return {"ok": False, "reason": f"交接单 {handover_id} 不存在"}
    material = None
    for row in _pending_rows():
        if int(row.get("id", 0)) == material_id:
            material = row
            break
    if material is None:
        return {"ok": False, "reason": f"物料 {material_id} 不存在"}
    if int(material.get("交接单", 0)) != handover_id:
        return {"ok": False, "reason": f"物料 {material_id} 不属于交接单 {handover_id}"}
    if not receiver_name.strip():
        return {"ok": False, "reason": "必须登记接收人才能把物料搬出展位"}
    if not receiver_enterprise.strip():
        return {"ok": False, "reason": "必须登记接收企业才能把物料搬出展位"}

    before = copy.deepcopy(material)
    material["清点状态"] = "已清点"
    material["接收企业"] = receiver_enterprise.strip()
    material["接收人"] = receiver_name.strip()
    material["status"] = "已确认"
    material["pending"] = False
    material["abnormal"] = False

    store.event_log.record(
        module="swap_handover",
        entry_id=handover_id,
        action="物料清点登记接收人",
        before=before,
        after=copy.deepcopy(material),
        extra={
            "booth_no": str(handover.get("展位编号", "")),
            "material_id": material_id,
            "box_no": material.get("箱号", ""),
            "receiver": material["接收人"],
            "receiver_enterprise": material["接收企业"],
            "operator": receiver_name,
        },
    )
    return {
        "ok": True,
        "reason": f"{material.get('箱号', '')} 已清点，接收人 {material['接收人']}",
        "material": material,
        "remaining_uncleared": [
            m.get("箱号") for m in uncleared_materials(handover_id)
        ],
        "entry_status": entry_status(handover_id),
    }


def settle_handover(handover_id: int) -> dict[str, Any]:
    """交方结算：原企业按原编号归档交出记录，回执状态随之转为已结算。"""
    handover = find_handover(handover_id)
    if handover is None:
        return {"ok": False, "reason": f"交接单 {handover_id} 不存在"}
    if str(handover.get("结算状态", "")) == "已结算":
        return {"ok": False, "reason": f"交接单 {handover_id} 已结算", "blocked": True}

    before = copy.deepcopy(handover)
    handover["结算状态"] = "已结算"
    settled_receipts = 0
    for receipt in _receipt_rows():
        if int(receipt.get("交接单", 0)) == handover_id and receipt.get("status") == "有效":
            receipt["status"] = "已结算"
            settled_receipts += 1

    store.event_log.record(
        module="swap_handover",
        entry_id=handover_id,
        action="交方结算归档",
        before=before,
        after=copy.deepcopy(handover),
        extra={
            "booth_no": str(handover.get("展位编号", "")),
            "outgoing_no": handover.get("交出编号", ""),
            "settled_receipts": settled_receipts,
        },
    )
    return {
        "ok": True,
        "reason": f"交接单 {handover_id} 已结算，{handover.get('交出编号', '')} 可继续按原编号查询交出记录",
        "handover": handover,
        "settled_receipts": settled_receipts,
    }


def outgoing_history(enterprise_no: str) -> dict[str, Any]:
    """已结算的原企业用原编号查自己的交出记录。"""
    code = enterprise_no.strip()
    handovers = [h for h in _handover_rows() if str(h.get("交出编号", "")) == code]
    if not handovers:
        return {"ok": False, "reason": f"编号 {code} 没有交出记录"}

    records: list[dict[str, Any]] = []
    for handover in handovers:
        handover_id = int(handover.get("id", 0))
        materials = material_by_handover(handover_id)
        receipts = [
            r for r in _receipt_rows() if int(r.get("交接单", 0)) == handover_id
        ]
        events = [
            e for e in store.event_log.for_module("swap_handover", handover_id)
            if e.get("action") in {"发放进场回执", "交方结算归档", "物料清点登记接收人"}
        ]
        records.append({
            "handover_id": handover_id,
            "booth_no": handover.get("展位编号", ""),
            "slot": handover.get("交接时段", ""),
            "outgoing_enterprise": handover.get("交出企业", ""),
            "outgoing_no": handover.get("交出编号", ""),
            "incoming_enterprise": handover.get("接手企业", ""),
            "incoming_no": handover.get("接手编号", ""),
            "交接状态": handover.get("交接状态", ""),
            "结算状态": handover.get("结算状态", ""),
            "materials": [
                {
                    "箱号": m.get("箱号"),
                    "物料名称": m.get("物料名称"),
                    "接收企业": m.get("接收企业") or "未登记",
                    "接收人": m.get("接收人") or "未登记",
                }
                for m in materials
            ],
            "receipts": [
                {"回执编号": r.get("回执编号"), "企业": r.get("企业"), "status": r.get("status")}
                for r in receipts
            ],
            "settled": str(handover.get("结算状态", "")) == "已结算",
            "events": [
                {"action": e.get("action"), "timestamp": e.get("timestamp")}
                for e in events
            ],
        })
    return {
        "ok": True,
        "enterprise_no": code,
        "record_count": len(records),
        "records": records,
    }


def record_by_no(enterprise_no: str) -> dict[str, Any]:
    """原编号统一查询入口：交出记录 + 作为接手方的接位回执。"""
    outgoing = outgoing_history(enterprise_no)
    code = enterprise_no.strip()
    incoming = [
        r for r in _receipt_rows() if str(r.get("企业编号", "")) == code
    ]
    return {
        "ok": outgoing.get("ok", False) or bool(incoming),
        "enterprise_no": code,
        "outgoing": outgoing,
        "incoming_receipts": [
            {
                "回执编号": r.get("回执编号"),
                "交接单": r.get("交接单"),
                "展位编号": r.get("展位编号"),
                "交接时段": r.get("交接时段"),
                "status": r.get("status"),
            }
            for r in incoming
        ],
    }


def duplicate_receipt_audit() -> dict[str, Any]:
    """核对有没有多发进场回执：同一（展位, 时段）有效回执不得超过 1 张。"""
    slots: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for receipt in _receipt_rows():
        if receipt.get("status") not in OCCUPYING_STATUSES:
            continue
        key = (str(receipt.get("展位编号", "")), str(receipt.get("交接时段", "")))
        slots.setdefault(key, []).append(receipt)

    duplicates = [
        {
            "booth_no": key[0],
            "slot": key[1],
            "count": len(items),
            "receipts": [r.get("回执编号") for r in items],
            "enterprises": [r.get("企业") for r in items],
        }
        for key, items in slots.items() if len(items) > 1
    ]
    return {
        "ok": len(duplicates) == 0,
        "checked_slots": len(slots),
        "duplicate_count": len(duplicates),
        "duplicates": duplicates,
    }
