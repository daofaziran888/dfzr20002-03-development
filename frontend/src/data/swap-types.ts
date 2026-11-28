/** 参展商换位交接类型：与后端 app/services/swap.py 返回结构一致。 */

export interface SwapHandover {
  id: number
  status: string
  pending: boolean
  abnormal: boolean
  展位编号: string
  交接时段: string
  交接时刻: string
  交出企业: string
  交出编号: string
  接手企业: string
  接手编号: string
  交接状态: string
  结算状态: string
  仓库催办: string
  接手申请进场: string
  登记编号: string
  负责人: string
  备注说明: string
}

export interface SwapMaterialView {
  id: number
  箱号: string
  物料名称: string
  数量: number
  清点状态: string
  接收企业: string
  接收人: string
  可搬出: boolean
}

export interface SwapParty {
  企业: string
  企业编号: string
  可进场: boolean
  说明?: string
  申请进场?: boolean
}

export interface SwapReceipt {
  回执编号: string
  企业: string
  企业编号: string
  展位编号: string
  交接时段: string
  关联物料: number[]
  status: string
}

export interface SwapEntryStatus {
  ok: boolean
  handover_id: number
  booth_no: string
  slot: string
  outgoing: SwapParty
  incoming: SwapParty
  materials: SwapMaterialView[]
  uncleared_count: number
  receipt: SwapReceipt | null
  receipt_count: number
  blockers: string[]
  can_issue: boolean
  conflict: boolean
  conflict_sides: { 仓库: string; 施工队: string; 结论: string }
  receipt_materials: { id: number; 箱号: string; 接收企业: string; 接收人: string }[]
}

export interface SwapIssueResult {
  ok: boolean
  reason: string
  receipt: SwapReceipt
  handover: SwapHandover
  materials: { 箱号: string; 物料名称: string; 接收人: string; 接收企业: string }[]
}

export interface SwapReleaseResult {
  ok: boolean
  reason: string
  remaining_uncleared: string[]
  entry_status: SwapEntryStatus
}

export interface SwapOutgoingRecord {
  handover_id: number
  booth_no: string
  slot: string
  outgoing_enterprise: string
  outgoing_no: string
  incoming_enterprise: string
  incoming_no: string
  交接状态: string
  结算状态: string
  materials: { 箱号: string; 物料名称: string; 接收企业: string; 接收人: string }[]
  receipts: { 回执编号: string; 企业: string; status: string }[]
  settled: boolean
  events: { action: string; timestamp: number }[]
}

export interface SwapRecordQuery {
  ok: boolean
  enterprise_no: string
  outgoing: { ok: boolean; enterprise_no: string; record_count: number; records: SwapOutgoingRecord[] }
  incoming_receipts: {
    回执编号: string
    交接单: number
    展位编号: string
    交接时段: string
    status: string
  }[]
}

export interface EntryReceiptAudit {
  ok: boolean
  checked_slots: number
  duplicate_count: number
  duplicates: { booth_no: string; slot: string; count: number; receipts: string[]; enterprises: string[] }[]
}
