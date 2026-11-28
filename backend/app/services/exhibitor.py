"""参展商管理领域服务：企业登记、合同金额与展位匹配校验，以及换位交接联动。

换位交接（进场回执、待交物料接收人、原编号交出记录查询）由 app.services.swap 承载，
本服务只在校验和快照里消费它的结论。
"""
from __future__ import annotations

from typing import Any

from app.services.base import BaseModuleService
from app.services import swap
from app.store import store


class ExhibitorService(BaseModuleService):
    MODULE = "exhibitor"
    ENTITY = "参展商"
    OPERATION_TERM = "确认参展"
    LIST_FIELDS = ["企业名称", "展品类别", "联系人", "合同金额", "登记编号", "负责人", "生效版本", "备注说明"]
    REQUIRED_FIELDS = ["企业名称", "展品类别", "联系人", "合同金额"]
    STATUS_ORDER = ["草稿", "待确认", "已确认", "已撤回"]
    ACTION_RULES = {"确认参展": "已确认", "提交确认": "待确认", "撤回记录": "已撤回"}
    NEGATIVE_ACTIONS = []
    RELATED_MODULES = ["booth", "material", "handover"]

    def validate_entry(self, values: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        try:
            amount = float(str(values.get("合同金额", "0")).replace("万元", "").replace(",", "").strip())
            if amount <= 0:
                errors.append("合同金额必须大于0")
        except (ValueError, AttributeError):
            errors.append("合同金额格式不正确")
        # 跨模块校验：参展商备注说明应引用有效展位编号
        remark = str(values.get("备注说明", "")).strip()
        if remark and remark.startswith("BOOT-"):
            booth = store.find_booth(remark)
            if booth is None:
                errors.append(f"展位 {remark} 不存在，请先登记展位")
        return errors

    def validate_action(self, entry_id: int, action: str) -> tuple[bool, str]:
        if action == "确认参展":
            entry = store.find(self.MODULE, entry_id)
            if entry is None:
                return False, "参展商不存在"
            # 检查关联展位是否已确认
            remark = str(entry.get("备注说明", ""))
            if remark.startswith("BOOT-"):
                booth = store.find_booth(remark)
                if booth and booth.get("status") != "已确认":
                    return False, f"关联展位 {remark} 尚未确认，参展商不能确认参展"
        return True, ""

    def domain_snapshot(self) -> dict[str, Any]:
        base = super().domain_snapshot()
        rows = self.related_rows("exhibitor")
        confirmed = [r for r in rows if r.get("status") == "已确认"]
        total_amount = 0.0
        for r in confirmed:
            try:
                total_amount += float(str(r.get("合同金额", "0")).replace("万元", "").replace(",", "").strip())
            except (ValueError, AttributeError):
                pass
        base["total_contract_amount"] = total_amount
        base["booth_linked"] = sum(
            1 for r in rows if str(r.get("备注说明", "")).startswith("BOOT-")
        )
        # 换位交接：待处理交接单与全场回执审计结论
        handovers = swap._handover_rows()
        open_handovers = [h for h in handovers if str(h.get("交接状态", "")) != "已交接"]
        base["swap_handovers"] = len(handovers)
        base["open_swap_handovers"] = len(open_handovers)
        base["receipt_audit_ok"] = swap.duplicate_receipt_audit()["ok"]
        return base