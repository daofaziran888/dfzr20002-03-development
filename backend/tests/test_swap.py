"""参展商换位交接：进场回执、物料接收人、原编号交出记录与回执不重发。

业务场景：甲（EXHI-0001/星辰科技）交出 BOOT-A01 时还有两箱材料未清点，
乙（EXHI-0004/远航智能）已到场申请接位；仓库催清料、施工队催进场，
两股诉求压在同一张交接单上。
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services import swap, service_for
from app.store import store

SLOT_A01 = "2026-09-19 08:00-12:00"


class SwapFixture(unittest.TestCase):
    """每个用例前把交接单1和相关数据恢复成"两箱未清点"的初始状态。"""

    def setUp(self):
        self.handover = store.find("swap_handover", 1)
        self.handover.update({
            "status": "待确认", "pending": True, "abnormal": True,
            "交接时段": SLOT_A01,
            "交接状态": "物料未清点", "结算状态": "未结算",
            "仓库催办": "是", "接手申请进场": "是",
        })
        for material_id in (1, 2):
            material = store.find("pending_material", material_id)
            material.update({
                "status": "待确认", "pending": True, "abnormal": True,
                "清点状态": "未清点", "接收企业": "", "接收人": "",
            })
        # 清掉 1 号交接单此前发放的回执，避免用例间串数据
        rows = store.rows("entry_receipt")
        rows[:] = [r for r in rows if int(r.get("交接单", 0)) != 1]
        store.rebuild_indices()


class TestSlotExclusivity(SwapFixture):
    """同一展位同一时段只能有一家可进场企业。"""

    def test_no_receipt_before_materials_cleared(self):
        """两箱未清点，乙申请进场也拿不到回执。"""
        result = swap.issue_entry_receipt(1)
        self.assertFalse(result["ok"])
        status = swap.entry_status(1)
        self.assertFalse(status["incoming"]["可进场"])
        self.assertTrue(status["conflict"])
        self.assertEqual(status["uncleared_count"], 2)

    def test_other_enterprise_holds_slot_blocks(self):
        """同展位同时段已有别家有效回执时，本交接单被拒。"""
        store.rows("entry_receipt").append({
            "id": store.next_id("entry_receipt"),
            "status": "有效", "pending": False, "abnormal": False,
            "回执编号": "RCPT-9001", "交接单": 99,
            "展位编号": "BOOT-A01", "交接时段": SLOT_A01,
            "企业": "占位企业", "企业编号": "EXHI-9001",
            "关联物料": [], "登记编号": "RCPT-9001",
            "负责人": "测试", "生效版本": "v1.0", "备注说明": "",
        })
        for material_id in (1, 2):
            swap.release_materials(1, material_id, "远航智能装备有限公司", "周工")
        result = swap.issue_entry_receipt(1)
        self.assertFalse(result["ok"])
        self.assertIn("同一时段只能一家进场", result["reason"])

    def test_different_slot_same_booth_allowed(self):
        """换到另一个时段后同一展位可以另发一张回执。"""
        for material_id in (1, 2):
            swap.release_materials(1, material_id, "远航智能装备有限公司", "周工")
        self.handover["交接时段"] = "2026-09-19 13:00-17:00"
        receipt_before = swap.issue_entry_receipt(1)
        self.assertTrue(receipt_before["ok"], receipt_before.get("reason"))
        self.assertTrue(swap.duplicate_receipt_audit()["ok"])


class TestPendingMaterialReceiver(SwapFixture):
    """搬出前还在展位里的物料必须能查到接收人。"""

    def test_uncleared_material_has_no_receiver(self):
        status = swap.entry_status(1)
        boxes = {m["箱号"]: m for m in status["materials"]}
        self.assertEqual(set(boxes), {"箱1", "箱2"})
        self.assertEqual(boxes["箱1"]["接收人"], "未登记")
        self.assertFalse(boxes["箱1"]["可搬出"])
        self.assertFalse(boxes["箱2"]["可搬出"])

    def test_release_requires_receiver(self):
        result = swap.release_materials(1, 1, "远航智能装备有限公司", "  ")
        self.assertFalse(result["ok"])

    def test_one_box_cleared_still_blocks_other(self):
        swap.release_materials(1, 1, "远航智能装备有限公司", "周工")
        result = swap.issue_entry_receipt(1)
        self.assertFalse(result["ok"])
        self.assertIn("箱2", result["reason"])
        self.assertIn("1 箱", result["reason"])

    def test_both_boxes_cleared_receipt_links_receivers(self):
        swap.release_materials(1, 1, "远航智能装备有限公司", "周工")
        swap.release_materials(1, 2, "远航智能装备有限公司", "周工")
        result = swap.issue_entry_receipt(1)
        self.assertTrue(result["ok"], result.get("reason"))
        receipt = result["receipt"]
        self.assertEqual(receipt["关联物料"], [1, 2])
        for row in result["materials"]:
            self.assertEqual(row["接收人"], "周工")
            self.assertEqual(row["接收企业"], "远航智能装备有限公司")


class TestNoDuplicateReceipt(SwapFixture):
    """重新提交同一交接时核对有没有多发进场回执。"""

    def test_resubmit_does_not_issue_second_receipt(self):
        for material_id in (1, 2):
            swap.release_materials(1, material_id, "远航智能装备有限公司", "周工")
        first = swap.issue_entry_receipt(1)
        self.assertTrue(first["ok"])
        receipt_no = first["receipt"]["回执编号"]
        second = swap.issue_entry_receipt(1)
        self.assertFalse(second["ok"])
        self.assertIn("不重复发放", second["reason"])
        self.assertEqual(second["receipt"]["回执编号"], receipt_no)
        self.assertEqual(
            len([r for r in store.rows("entry_receipt") if int(r.get("交接单", 0)) == 1]), 1)
        self.assertTrue(swap.duplicate_receipt_audit()["ok"])

    def test_audit_flags_planted_duplicate(self):
        for material_id in (1, 2):
            swap.release_materials(1, material_id, "远航智能装备有限公司", "周工")
        first = swap.issue_entry_receipt(1)
        self.assertTrue(first["ok"])
        store.rows("entry_receipt").append({
            "id": store.next_id("entry_receipt"),
            "status": "有效", "pending": False, "abnormal": False,
            "回执编号": "RCPT-9002", "交接单": 1,
            "展位编号": "BOOT-A01", "交接时段": SLOT_A01,
            "企业": "远航智能装备有限公司", "企业编号": "EXHI-0004",
            "关联物料": [1, 2], "登记编号": "RCPT-9002",
            "负责人": "测试", "生效版本": "v1.0", "备注说明": "人为多发的重复回执",
        })
        audit = swap.duplicate_receipt_audit()
        self.assertFalse(audit["ok"])
        self.assertEqual(audit["duplicate_count"], 1)
        self.assertEqual(audit["duplicates"][0]["booth_no"], "BOOT-A01")


class TestSettledOutgoingLookup(unittest.TestCase):
    """已结算的前一家企业用原编号还能查自己的交出记录。"""

    def test_settled_a02_query_by_original_no(self):
        result = swap.record_by_no("EXHI-0002")
        self.assertTrue(result["ok"])
        self.assertEqual(result["outgoing"]["record_count"], 1)
        record = result["outgoing"]["records"][0]
        self.assertTrue(record["settled"])
        self.assertEqual(record["booth_no"], "BOOT-A02")
        self.assertEqual(record["outgoing_enterprise"], "墨韵文化传播")

    def test_unknown_no_has_no_record(self):
        self.assertFalse(swap.record_by_no("EXHI-9999")["ok"])


class TestEntryStatusConflict(SwapFixture):
    """同一张交接单上仓库催料与施工队催进场同时可见。"""

    def test_both_sides_visible(self):
        status = swap.entry_status(1)
        self.assertIn("仓库", status["conflict_sides"])
        self.assertIn("施工队", status["conflict_sides"])
        self.assertEqual(status["conflict_sides"]["仓库"], "催交出方交清两箱材料")

    def test_incoming_cannot_enter_while_outgoing_holds_materials(self):
        status = swap.entry_status(1)
        self.assertFalse(status["outgoing"]["可进场"])
        self.assertFalse(status["incoming"]["可进场"])


class TestExhibitorSnapshot(unittest.TestCase):
    """参展商管理快照消费换位交接结论。"""

    def test_snapshot_reports_swap_and_audit(self):
        snap = service_for("exhibitor").domain_snapshot()
        self.assertEqual(snap["swap_handovers"], 2)
        self.assertIn("open_swap_handovers", snap)
        self.assertTrue(snap["receipt_audit_ok"])

    def test_internal_tables_not_counted_as_modules(self):
        self.assertEqual(len(store.module_names()), 18)
        for internal in ("swap_handover", "pending_material", "entry_receipt"):
            self.assertNotIn(internal, store.module_names())


if __name__ == "__main__":
    unittest.main(verbosity=2)
