<template>
  <section class="panel-block" data-testid="trial-dispatch-panel">
    <h3>试采派工（消费采集接入清单）</h3>
    <p class="panel-desc">
      输入爬虫配置导入来源清单得到的回执编号发起试采：只派工核对通过的来源，
      已受理的试采不重发，待查来源保留待查原因等补证后恢复。
    </p>
    <form class="filter-bar" @submit.prevent="submitDispatch">
      <label class="filter-item">
        <span>导入回执编号</span>
        <input v-model="receiptId" data-testid="dispatch-receipt" placeholder="如 IMP-0001" />
      </label>
      <label class="filter-item">
        <span>操作人</span>
        <input v-model="operator" data-testid="dispatch-operator" placeholder="值班员" />
      </label>
      <button class="btn primary" data-testid="dispatch-submit" type="submit" :disabled="dispatching">
        {{ dispatching ? '派工中…' : '提交试采' }}
      </button>
    </form>
    <p v-if="dispatchMessage" class="panel-message" data-testid="dispatch-message">{{ dispatchMessage }}</p>

    <div v-if="dispatchResult" class="dispatch-result" data-testid="dispatch-result">
      <h4>本次派工（{{ dispatchResult.本次派工.length }}）</h4>
      <table class="data-table">
        <thead>
          <tr><th>试采编号</th><th>清单行号</th><th>来源别名</th><th>起始地址</th><th>页面编码</th><th>状态</th><th>派工时间</th></tr>
        </thead>
        <tbody>
          <tr v-for="item in dispatchResult.本次派工" :key="item.试采编号">
            <td>{{ item.试采编号 }}</td>
            <td>{{ item.清单行号 }}</td>
            <td>{{ item.来源别名 }}</td>
            <td>{{ item.起始地址 }}</td>
            <td>{{ item.页面编码 }}</td>
            <td class="status-ok">{{ item.状态 }}</td>
            <td>{{ item.派工时间 }}</td>
          </tr>
          <tr v-if="!dispatchResult.本次派工.length">
            <td colspan="7" class="empty-state">本次没有新派工的来源</td>
          </tr>
        </tbody>
      </table>

      <h4>已受理未重发（{{ dispatchResult.已受理未重发.length }}）</h4>
      <table class="data-table">
        <thead>
          <tr><th>试采编号</th><th>清单行号</th><th>来源别名</th><th>起始地址</th><th>页面编码</th><th>首次派工时间</th></tr>
        </thead>
        <tbody>
          <tr v-for="item in dispatchResult.已受理未重发" :key="item.试采编号">
            <td>{{ item.试采编号 }}</td>
            <td>{{ item.清单行号 }}</td>
            <td>{{ item.来源别名 }}</td>
            <td>{{ item.起始地址 }}</td>
            <td>{{ item.页面编码 }}</td>
            <td>{{ item.派工时间 }}</td>
          </tr>
          <tr v-if="!dispatchResult.已受理未重发.length">
            <td colspan="6" class="empty-state">没有此前已受理的来源</td>
          </tr>
        </tbody>
      </table>

      <h4>待补证（{{ dispatchResult.待补证.length }}）</h4>
      <table class="data-table">
        <thead>
          <tr><th>清单行号</th><th>来源别名</th><th>起始地址</th><th>页面编码</th><th>待查原因</th></tr>
        </thead>
        <tbody>
          <tr v-for="item in dispatchResult.待补证" :key="item.行号">
            <td>{{ item.行号 }}</td>
            <td>{{ item.来源别名 }}</td>
            <td>{{ item.起始地址 }}</td>
            <td>{{ item.页面编码 }}</td>
            <td class="status-pending">{{ item.待查原因 }}</td>
          </tr>
          <tr v-if="!dispatchResult.待补证.length">
            <td colspan="5" class="empty-state">没有待补证的来源</td>
          </tr>
        </tbody>
      </table>
    </div>

    <h3>试采请求核查（另一入口：实际收到的试采请求及其原清单行）</h3>
    <form class="filter-bar" @submit.prevent="loadTrials">
      <label class="filter-item">
        <span>按回执编号过滤（可空）</span>
        <input v-model="trialFilter" data-testid="trial-filter" placeholder="如 IMP-0001" />
      </label>
      <button class="btn" data-testid="trial-query" type="submit">核查试采请求</button>
    </form>
    <table class="data-table">
      <thead>
        <tr><th>试采编号</th><th>回执编号</th><th>清单行号</th><th>来源别名</th><th>起始地址</th><th>页面编码</th><th>状态</th><th>派工时间</th><th>原清单行</th></tr>
      </thead>
      <tbody>
        <tr v-for="item in trials" :key="item.试采编号" :data-testid="`trial-${item.试采编号}`">
          <td>{{ item.试采编号 }}</td>
          <td>{{ item.回执编号 }}</td>
          <td>{{ item.清单行号 }}</td>
          <td>{{ item.来源别名 }}</td>
          <td>{{ item.起始地址 }}</td>
          <td>{{ item.页面编码 }}</td>
          <td>{{ item.状态 }}</td>
          <td>{{ item.派工时间 }}</td>
          <td class="raw-line">{{ item.原清单行 }}</td>
        </tr>
        <tr v-if="!trials.length">
          <td colspan="9" class="empty-state">暂无试采请求，可先从导入回执提交试采</td>
        </tr>
      </tbody>
    </table>
    <p class="panel-desc">共 {{ trialTotal }} 条试采请求</p>

    <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import {
  dispatchTrial,
  listTrialRequests,
  type DispatchResult,
  type TrialRequest,
} from '@/api/intake-service'

const receiptId = ref('')
const operator = ref('值班员')
const dispatching = ref(false)
const dispatchMessage = ref('')
const dispatchResult = ref<DispatchResult | null>(null)
const trialFilter = ref('')
const trials = ref<TrialRequest[]>([])
const trialTotal = ref(0)
const errorMessage = ref('')

async function submitDispatch() {
  if (!receiptId.value.trim()) {
    errorMessage.value = '请输入导入回执编号'
    return
  }
  dispatching.value = true
  errorMessage.value = ''
  dispatchMessage.value = ''
  try {
    const result = await dispatchTrial(receiptId.value.trim(), operator.value)
    dispatchResult.value = result
    dispatchMessage.value = result.message
    trialFilter.value = receiptId.value.trim()
    await loadTrials()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '试采派工失败'
  } finally {
    dispatching.value = false
  }
}

async function loadTrials() {
  errorMessage.value = ''
  try {
    const result = await listTrialRequests(trialFilter.value.trim())
    trials.value = result.items
    trialTotal.value = result.total
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '试采请求核查失败'
  }
}

onMounted(loadTrials)
</script>
