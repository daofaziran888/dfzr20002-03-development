/** 参展商换位交接 API：进场状态、物料接收人、回执发放、原编号交出记录。 */
import { request } from './client'
import type {
  EntryReceiptAudit,
  SwapEntryStatus,
  SwapHandover,
  SwapIssueResult,
  SwapRecordQuery,
  SwapReleaseResult,
} from '@/data/swap-types'

const SWAP_BASE = '/api/swap'

async function readJson<T>(response: Response, fallback: string): Promise<T> {
  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = payload && typeof payload === 'object' ? (payload as { detail?: string }).detail : ''
    throw new Error(detail || fallback)
  }
  return payload as T
}

export async function fetchSwapHandovers(): Promise<{ items: SwapHandover[]; total: number }> {
  return readJson(await request(`${SWAP_BASE}/handovers`), '交接单读取失败')
}

export async function fetchEntryStatus(handoverId: number): Promise<SwapEntryStatus> {
  return readJson(await request(`${SWAP_BASE}/handover/${handoverId}/status`), '进场状态读取失败')
}

export async function issueEntryReceipt(handoverId: number): Promise<SwapIssueResult> {
  return readJson(
    await request(`${SWAP_BASE}/handover/${handoverId}/receipt`, { method: 'POST' }),
    '进场回执发放失败',
  )
}

export async function releaseMaterial(
  handoverId: number,
  materialId: number,
  receiverEnterprise: string,
  receiverName: string,
): Promise<SwapReleaseResult> {
  const query = new URLSearchParams({
    receiver_enterprise: receiverEnterprise,
    receiver_name: receiverName,
  }).toString()
  return readJson(
    await request(`${SWAP_BASE}/handover/${handoverId}/material/${materialId}/release?${query}`, {
      method: 'POST',
    }),
    '物料清点登记失败',
  )
}

export async function settleHandover(handoverId: number): Promise<{ ok: boolean; reason: string }> {
  return readJson(
    await request(`${SWAP_BASE}/handover/${handoverId}/settle`, { method: 'POST' }),
    '结算失败',
  )
}

export async function fetchRecordByNo(enterpriseNo: string): Promise<SwapRecordQuery> {
  return readJson(
    await request(`${SWAP_BASE}/records/${encodeURIComponent(enterpriseNo)}`),
    '原编号交出记录查询失败',
  )
}

export async function fetchReceiptAudit(): Promise<EntryReceiptAudit> {
  return readJson(await request(`${SWAP_BASE}/receipt-audit`), '回执审计读取失败')
}
