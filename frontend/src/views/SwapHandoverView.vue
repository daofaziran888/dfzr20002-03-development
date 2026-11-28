<template>
  <section class="page" data-module="swap">
    <header class="page-head">
      <div>
        <h2>参展商换位交接</h2>
        <p class="page-desc">
          按展位和待交物料给接手企业发放进场回执；同一展位同一时段只能一家可进场，搬出前物料必须登记接收人。
        </p>
      </div>
      <div class="page-actions">
        <button class="btn" data-testid="refresh-swap" type="button" @click="refresh">刷新交接单</button>
      </div>
    </header>

    <div class="stat-row">
      <article class="stat-card">
        <span class="stat-label">交接单总数</span>
        <strong class="stat-value">{{ handovers.length }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">有冲突待处理</span>
        <strong class="stat-value">{{ status?.conflict ? 1 : 0 }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">待交物料未清点</span>
        <strong class="stat-value">{{ status?.uncleared_count ?? 0 }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">回执发放</span>
        <strong class="stat-value">{{ status?.receipt_count ?? 0 }}</strong>
      </article>
    </div>

    <p v-if="errorMessage" class="error-text" data-testid="swap-error">{{ errorMessage }}</p>
    <p v-if="successMessage" class="success-text" data-testid="swap-success">{{ successMessage }}</p>

    <!-- 交接单切换 -->
    <form class="filter-bar" @submit.prevent="loadHandover">
      <label class="filter-item">
        <span>交接单</span>
        <select v-model.number="selectedId" data-testid="swap-select">
          <option v-for="item in handovers" :key="item.id" :value="item.id">
            #{{ item.id }} {{ item.展位编号 }} {{ item.交接时段 }}（{{ item.交接状态 }}）
          </option>
        </select>
      </label>
      <button class="btn primary" data-testid="load-swap" type="submit">查看交接单</button>
    </form>

    <div v-if="status" class="swap-view">
      <!-- 两边诉求冲突 -->
      <section class="info-card conflict-card" data-testid="conflict-card">
        <h4>同一张交接单上的两股诉求</h4>
        <p>
          <span class="tag">{{ status.conflict_sides.仓库 }}</span>
          <span class="tag">{{ status.conflict_sides.施工队 }}</span>
        </p>
        <p :class="status.conflict ? 'text-danger' : 'text-success'" data-testid="conflict-conclusion">
          {{ status.conflict_sides.结论 }}
        </p>
        <ul v-if="status.blockers.length" class="blocker-list">
          <li v-for="(reason, idx) in status.blockers" :key="idx" data-testid="swap-blocker">{{ reason }}</li>
        </ul>
      </section>

      <!-- 甲/乙进场状态 -->
      <section class="info-card">
        <h4>双方进场状态（{{ status.booth_no }} / {{ status.slot }}）</h4>
        <div class="party-grid">
          <article class="party-card" data-testid="outgoing-party">
            <span class="party-label">交出方 甲</span>
            <strong>{{ status.outgoing.企业 }}</strong>
            <span class="party-no">{{ status.outgoing.企业编号 }}</span>
            <span class="party-state" :class="status.outgoing.可进场 ? 'text-success' : 'text-danger'">
              {{ status.outgoing.可进场 ? '可进场' : '不可进场' }}
            </span>
            <small>{{ status.outgoing.说明 }}</small>
          </article>
          <article class="party-card" data-testid="incoming-party">
            <span class="party-label">接手方 乙</span>
            <strong>{{ status.incoming.企业 }}</strong>
            <span class="party-no">{{ status.incoming.企业编号 }}</span>
            <span class="party-state" :class="status.incoming.可进场 ? 'text-success' : 'text-danger'">
              {{ status.incoming.可进场 ? '可进场' : '未获准进场' }}
            </span>
            <small>{{ status.incoming.申请进场 ? '已到场申请接位' : '未申请进场' }}</small>
          </article>
        </div>
        <div class="page-actions" style="margin-top: 12px">
          <button
            class="btn primary"
            data-testid="issue-receipt"
            type="button"
            :disabled="!status.can_issue || busy"
            @click="issueReceipt"
          >
            {{ status.receipt ? '已发放回执' : '发放进场回执' }}
          </button>
        </div>
      </section>

      <!-- 与回执关联的待交物料接收人 -->
      <section class="info-card">
        <h4>待交物料接收人</h4>
        <table class="data-table">
          <thead>
            <tr><th>箱号</th><th>物料名称</th><th>数量</th><th>清点状态</th><th>接收企业</th><th>接收人</th><th>操作</th></tr>
          </thead>
          <tbody>
            <tr v-for="material in status.materials" :key="material.id" :data-testid="`material-${material.id}`">
              <td>{{ material.箱号 }}</td>
              <td>{{ material.物料名称 }}</td>
              <td>{{ material.数量 }}</td>
              <td>{{ material.清点状态 }}</td>
              <td>{{ material.接收企业 }}</td>
              <td data-testid="material-receiver">{{ material.接收人 }}</td>
              <td>
                <button
                  v-if="!material.可搬出"
                  class="link"
                  type="button"
                  :data-testid="`release-${material.id}`"
                  @click="openRelease(material)"
                >
                  清点并登记接收人
                </button>
                <span v-else class="text-success">可搬出</span>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-if="status.receipt" class="receipt-box" data-testid="receipt-box">
          <p>
            回执 <strong>{{ status.receipt.回执编号 }}</strong> → {{ status.receipt.企业 }}
            （{{ status.receipt.status }}），关联物料 {{ status.receipt.关联物料.join('、') }}
          </p>
          <p v-for="item in status.receipt_materials" :key="item.id">
            {{ item.箱号 }} 接收人：{{ item.接收人 }}（{{ item.接收企业 }}）
          </p>
        </div>
      </section>
    </div>

    <!-- 回执审计 -->
    <section class="info-card">
      <h4>进场回执核对</h4>
      <p :class="audit?.ok ? 'text-success' : 'text-danger'" data-testid="audit-summary">
        {{ audit?.ok ? '同一展位同一时段未发现多发回执' : `发现 ${audit?.duplicate_count} 个时段重复发放` }}
        （已核 {{ audit?.checked_slots ?? 0 }} 个时段）
      </p>
    </section>

    <!-- 原编号查询 -->
    <section class="info-card">
      <h4>按原编号查询交出记录</h4>
      <form class="filter-bar" @submit.prevent="queryByNo">
        <label class="filter-item">
          <span>企业编号</span>
          <input v-model="enterpriseNo" placeholder="如 EXHI-0002" data-testid="enterprise-no" />
        </label>
        <button class="btn primary" data-testid="query-records" type="submit">查询交出记录</button>
      </form>
      <div v-if="recordQuery" data-testid="record-result">
        <p v-if="recordQuery.outgoing.ok">
          编号 {{ recordQuery.enterprise_no }} 共 {{ recordQuery.outgoing.record_count }} 条交出记录
        </p>
        <article
          v-for="record in recordQuery.outgoing.records"
          :key="record.handover_id"
          class="record-card"
        >
          <p>
            <strong>{{ record.booth_no }}</strong> {{ record.slot }}
            ｜{{ record.outgoing_enterprise }} → {{ record.incoming_enterprise }}
            ｜{{ record.结算状态 }}
          </p>
          <p v-for="(material, idx) in record.materials" :key="idx">
            {{ material.箱号 }} {{ material.物料名称 }} → {{ material.接收人 }}（{{ material.接收企业 }}）
          </p>
          <p v-if="record.receipts.length">
            回执：{{ record.receipts.map((r) => `${r.回执编号}(${r.status})`).join('、') }}
          </p>
        </article>
      </div>
    </section>

    <!-- 清点登记弹窗 -->
    <div v-if="releaseTarget" class="modal-backdrop" data-testid="release-modal">
      <form class="modal" @submit.prevent="submitRelease">
        <h3>清点 {{ releaseTarget.箱号 }} 并登记接收人</h3>
        <label class="create-field">
          <span>接收企业</span>
          <input v-model="releaseForm.receiverEnterprise" data-testid="release-enterprise" required />
        </label>
        <label class="create-field">
          <span>接收人</span>
          <input v-model="releaseForm.receiverName" data-testid="release-name" required />
        </label>
        <div class="page-actions">
          <button class="btn" type="button" @click="releaseTarget = null">取消</button>
          <button class="btn primary" data-testid="submit-release" type="submit" :disabled="busy">
            {{ busy ? '提交中…' : '确认登记' }}
          </button>
        </div>
      </form>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import {
  fetchEntryStatus,
  fetchReceiptAudit,
  fetchRecordByNo,
  fetchSwapHandovers,
  issueEntryReceipt,
  releaseMaterial,
} from '@/api/swap-client'
import type {
  EntryReceiptAudit,
  SwapEntryStatus,
  SwapHandover,
  SwapMaterialView,
  SwapRecordQuery,
} from '@/data/swap-types'

const handovers = ref<SwapHandover[]>([])
const selectedId = ref(1)
const status = ref<SwapEntryStatus | null>(null)
const audit = ref<EntryReceiptAudit | null>(null)
const errorMessage = ref('')
const successMessage = ref('')
const busy = ref(false)
const enterpriseNo = ref('EXHI-0002')
const recordQuery = ref<SwapRecordQuery | null>(null)
const releaseTarget = ref<SwapMaterialView | null>(null)
const releaseForm = ref({ receiverEnterprise: '', receiverName: '' })

function showError(error: unknown, fallback: string) {
  errorMessage.value = error instanceof Error ? error.message : fallback
  successMessage.value = ''
}

async function loadStatus(id: number) {
  status.value = await fetchEntryStatus(id)
}

async function refresh() {
  errorMessage.value = ''
  try {
    const payload = await fetchSwapHandovers()
    handovers.value = payload.items
    audit.value = await fetchReceiptAudit()
    await loadStatus(selectedId.value)
  } catch (error) {
    showError(error, '交接单读取失败')
  }
}

async function loadHandover() {
  errorMessage.value = ''
  successMessage.value = ''
  try {
    await loadStatus(selectedId.value)
    audit.value = await fetchReceiptAudit()
  } catch (error) {
    showError(error, '交接单读取失败')
  }
}

function openRelease(material: SwapMaterialView) {
  releaseTarget.value = material
  releaseForm.value = {
    receiverEnterprise: status.value?.incoming.企业 ?? '',
    receiverName: '',
  }
}

async function submitRelease() {
  if (!releaseTarget.value) return
  busy.value = true
  errorMessage.value = ''
  successMessage.value = ''
  try {
    const result = await releaseMaterial(
      selectedId.value,
      releaseTarget.value.id,
      releaseForm.value.receiverEnterprise,
      releaseForm.value.receiverName,
    )
    successMessage.value = result.reason
    releaseTarget.value = null
    await loadStatus(selectedId.value)
  } catch (error) {
    showError(error, '物料清点登记失败')
  } finally {
    busy.value = false
  }
}

async function issueReceipt() {
  busy.value = true
  errorMessage.value = ''
  successMessage.value = ''
  try {
    const result = await issueEntryReceipt(selectedId.value)
    successMessage.value = result.reason
    await loadStatus(selectedId.value)
    audit.value = await fetchReceiptAudit()
  } catch (error) {
    showError(error, '进场回执发放失败')
  } finally {
    busy.value = false
  }
}

async function queryByNo() {
  errorMessage.value = ''
  try {
    recordQuery.value = await fetchRecordByNo(enterpriseNo.value.trim())
  } catch (error) {
    recordQuery.value = null
    showError(error, '原编号交出记录查询失败')
  }
}

onMounted(refresh)
</script>

<style scoped>
.info-card {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
}
.info-card h4 { margin: 0 0 10px; color: #333; }
.conflict-card { background: #fff7e6; }
.tag {
  display: inline-block; margin-right: 8px; padding: 2px 10px;
  background: #fff; border: 1px solid #ffd591; border-radius: 12px;
  font-size: 12px; color: #ad6800;
}
.blocker-list { margin: 8px 0 0; padding-left: 18px; color: #b42318; font-size: 13px; }
.party-grid { display: flex; gap: 12px; flex-wrap: wrap; }
.party-card {
  flex: 1; min-width: 220px; display: flex; flex-direction: column; gap: 4px;
  background: #fff; border: 1px solid #d8dee6; border-radius: 8px; padding: 12px;
}
.party-label { font-size: 12px; color: #64748b; }
.party-no { font-size: 12px; color: #94a3b8; }
.party-state { font-size: 13px; font-weight: 600; }
.party-card small { color: #64748b; font-size: 12px; }
.receipt-box {
  margin-top: 12px; padding: 10px; background: #f6ffed;
  border: 1px solid #b7eb8f; border-radius: 6px; font-size: 13px;
}
.record-card {
  background: #fff; border: 1px solid #d8dee6; border-radius: 6px;
  padding: 10px; margin-top: 8px; font-size: 13px;
}
.text-success { color: #52c41a; }
.text-danger { color: #f5222d; }
.success-text { color: #52c41a; }
</style>
