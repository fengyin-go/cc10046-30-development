<template>
  <section class="panel-block" data-testid="source-intake-panel">
    <h3>来源清单导入（本地原页核对地址与编码）</h3>
    <p class="panel-desc">
      粘贴来源清单 CSV（需含 来源别名、起始地址、页面编码 三列），同名来源按真实起始地址区分；
      可为来源随附本地原页样本，导入时逐行核对地址与编码，生成采集接入清单和导入回执。
    </p>
    <form class="filter-bar" @submit.prevent="submitImport">
      <label class="filter-item intake-csv">
        <span>来源清单 CSV</span>
        <textarea
          v-model="csvText"
          data-testid="import-csv"
          rows="4"
          placeholder="来源别名,起始地址,页面编码&#10;晨讯早报,https://news.example.com/main,utf-8&#10;晨讯早报,https://news.example.com/branch,gbk"
        ></textarea>
      </label>
      <label class="filter-item">
        <span>导入人</span>
        <input v-model="operator" data-testid="import-operator" placeholder="值班员" />
      </label>
    </form>

    <div class="sample-rows">
      <div v-for="(sample, index) in samples" :key="index" class="sample-row">
        <input v-model="sample.起始地址" :data-testid="`sample-address-${index}`" placeholder="随附样本的起始地址" />
        <input v-model="sample.页面编码" :data-testid="`sample-encoding-${index}`" placeholder="样本编码，如 utf-8" />
        <label class="file-picker">
          <input type="file" :data-testid="`sample-file-${index}`" @change="onSampleFile($event, sample)" />
          <span>{{ sample.文件名 || '选择本地原页文件' }}</span>
        </label>
        <button class="btn ghost" type="button" @click="samples.splice(index, 1)">移除</button>
      </div>
      <button class="btn" type="button" data-testid="add-sample" @click="addSample">添加随附原页样本</button>
    </div>

    <div class="page-actions">
      <button class="btn primary" type="button" data-testid="submit-import" :disabled="importing" @click="submitImport">
        {{ importing ? '导入中…' : '导入来源清单' }}
      </button>
      <span v-if="importMessage" class="panel-message">{{ importMessage }}</span>
    </div>

    <div v-if="lastReceipt" class="receipt-result" data-testid="import-receipt">
      <h4>
        导入回执 {{ lastReceipt.回执编号 }}：共 {{ lastReceipt.汇总.清单行数 }} 行，
        核对通过 {{ lastReceipt.汇总.核对通过 }} 行，待查 {{ lastReceipt.汇总.待查 }} 行
      </h4>
      <table class="data-table">
        <thead>
          <tr><th>行号</th><th>来源别名</th><th>起始地址</th><th>页面编码</th><th>核对状态</th><th>待查原因 / 原页标题</th></tr>
        </thead>
        <tbody>
          <tr v-for="row in lastReceipt.清单行" :key="row.行号" :data-status="row.核对状态">
            <td>{{ row.行号 }}</td>
            <td>{{ row.来源别名 }}</td>
            <td>{{ row.起始地址 }}</td>
            <td>{{ row.页面编码 }}</td>
            <td :class="row.核对状态 === '核对通过' ? 'status-ok' : 'status-pending'">{{ row.核对状态 }}</td>
            <td>{{ row.核对状态 === '核对通过' ? row.原页标题 || '—' : row.待查原因 }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <h3>导入回执（补证后旧回执保持可查）</h3>
    <table class="data-table">
      <thead>
        <tr><th>回执编号</th><th>导入时间</th><th>导入人</th><th>清单行数</th><th>核对通过</th><th>待查</th><th>补证记录</th><th>操作</th></tr>
      </thead>
      <tbody>
        <tr v-for="receipt in receipts" :key="receipt.回执编号" :data-testid="`receipt-${receipt.回执编号}`">
          <td>{{ receipt.回执编号 }}</td>
          <td>{{ receipt.导入时间 }}</td>
          <td>{{ receipt.导入人 }}</td>
          <td>{{ receipt.汇总.清单行数 }}</td>
          <td>{{ receipt.汇总.核对通过 }}</td>
          <td>{{ receipt.汇总.待查 }}</td>
          <td>{{ receipt.补证记录.length ? `${receipt.补证记录.length} 次补证` : '—' }}</td>
          <td>
            <button class="link" type="button" :data-testid="`view-${receipt.回执编号}`" @click="loadReceipt(receipt.回执编号)">
              查看清单
            </button>
          </td>
        </tr>
        <tr v-if="!receipts.length">
          <td colspan="8" class="empty-state">暂无导入回执，可先导入来源清单</td>
        </tr>
      </tbody>
    </table>

    <div v-if="selectedReceipt" class="receipt-result" data-testid="receipt-detail">
      <h4>采集接入清单 {{ selectedReceipt.回执编号 }}（采集调度只读取核对通过的来源）</h4>
      <table class="data-table">
        <thead>
          <tr><th>行号</th><th>来源别名</th><th>起始地址</th><th>页面编码</th><th>核对状态</th><th>待查原因</th><th>核对记录</th><th>补证</th></tr>
        </thead>
        <tbody>
          <tr v-for="row in selectedReceipt.清单行" :key="row.行号" :data-testid="`intake-row-${row.行号}`" :data-status="row.核对状态">
            <td>{{ row.行号 }}</td>
            <td>{{ row.来源别名 }}</td>
            <td>{{ row.起始地址 }}</td>
            <td>{{ row.页面编码 }}</td>
            <td :class="row.核对状态 === '核对通过' ? 'status-ok' : 'status-pending'">{{ row.核对状态 }}</td>
            <td>{{ row.待查原因 || '—' }}</td>
            <td>
              <span v-for="(log, i) in row.核对记录" :key="i" class="audit-log">
                {{ log.时间 }} {{ log.结果 }}（{{ log.说明 }}）
              </span>
            </td>
            <td>
              <button
                v-if="row.核对状态 === '待查'"
                class="link"
                type="button"
                :data-testid="`supplement-open-${row.行号}`"
                @click="openSupplement(row)"
              >
                补交原页样本
              </button>
              <span v-else>—</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="supplementRow" class="modal-backdrop" data-testid="supplement-modal">
      <form class="modal" @submit.prevent="submitSupplement">
        <h3>补交本地原页样本</h3>
        <p class="panel-desc">
          回执 {{ selectedReceipt?.回执编号 }} 第 {{ supplementRow.行号 }} 行：
          {{ supplementRow.来源别名 }}（{{ supplementRow.起始地址 }}），声明编码 {{ supplementRow.页面编码 }}。
        </p>
        <label class="create-field">
          <span>本地原页文件（按声明编码核对）</span>
          <input type="file" data-testid="supplement-file" required @change="onSupplementFile" />
        </label>
        <div class="page-actions">
          <button class="btn" type="button" @click="supplementRow = null">取消</button>
          <button class="btn primary" data-testid="supplement-submit" type="submit" :disabled="supplementing">
            {{ supplementing ? '提交中…' : '提交补证' }}
          </button>
        </div>
        <span v-if="supplementError" class="error-text">{{ supplementError }}</span>
      </form>
    </div>

    <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import {
  getSourceImport,
  importSourceList,
  listSourceImports,
  readFileAsBase64,
  supplementSample,
  type ImportReceipt,
  type IntakeRow,
  type ReceiptSummary,
  type SampleInput,
} from '@/api/intake-service'

type SampleEntry = SampleInput & { 文件名: string }

const csvText = ref('')
const operator = ref('值班员')
const samples = ref<SampleEntry[]>([])
const importing = ref(false)
const importMessage = ref('')
const errorMessage = ref('')
const lastReceipt = ref<ImportReceipt | null>(null)
const receipts = ref<ReceiptSummary[]>([])
const selectedReceipt = ref<ImportReceipt | null>(null)
const supplementRow = ref<IntakeRow | null>(null)
const supplementFile = ref<{ name: string; content: string } | null>(null)
const supplementing = ref(false)
const supplementError = ref('')

function addSample() {
  samples.value.push({ 起始地址: '', 页面编码: '', 原页内容: '', 文件名: '' })
}

async function onSampleFile(event: Event, sample: SampleEntry) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  sample.原页内容 = await readFileAsBase64(file)
  sample.文件名 = file.name
}

async function submitImport() {
  if (!csvText.value.trim()) {
    errorMessage.value = '请先粘贴来源清单 CSV'
    return
  }
  importing.value = true
  errorMessage.value = ''
  importMessage.value = ''
  try {
    const usable = samples.value.filter((s) => s.起始地址.trim() && s.原页内容)
    const result = await importSourceList(csvText.value, usable, operator.value)
    lastReceipt.value = result.回执
    selectedReceipt.value = result.回执
    importMessage.value = result.message
    await reloadReceipts()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '来源清单导入失败'
  } finally {
    importing.value = false
  }
}

async function reloadReceipts() {
  const result = await listSourceImports()
  receipts.value = result.items
}

async function loadReceipt(receiptId: string) {
  errorMessage.value = ''
  try {
    const result = await getSourceImport(receiptId)
    selectedReceipt.value = result.回执
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '采集接入清单读取失败'
  }
}

function openSupplement(row: IntakeRow) {
  supplementRow.value = row
  supplementFile.value = null
  supplementError.value = ''
}

async function onSupplementFile(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  supplementFile.value = { name: file.name, content: await readFileAsBase64(file) }
}

async function submitSupplement() {
  if (!selectedReceipt.value || !supplementRow.value) return
  if (!supplementFile.value) {
    supplementError.value = '请选择本地原页文件'
    return
  }
  supplementing.value = true
  supplementError.value = ''
  try {
    await supplementSample(
      selectedReceipt.value.回执编号,
      {
        起始地址: supplementRow.value.起始地址,
        页面编码: supplementRow.value.页面编码,
        原页内容: supplementFile.value.content,
      },
      operator.value,
    )
    supplementRow.value = null
    await loadReceipt(selectedReceipt.value.回执编号)
    await reloadReceipts()
    if (lastReceipt.value && selectedReceipt.value &&
        lastReceipt.value.回执编号 === selectedReceipt.value.回执编号) {
      lastReceipt.value = selectedReceipt.value
    }
  } catch (error) {
    supplementError.value = error instanceof Error ? error.message : '补证样本提交失败'
  } finally {
    supplementing.value = false
  }
}

onMounted(reloadReceipts)
</script>
