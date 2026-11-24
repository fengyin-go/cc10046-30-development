/** 来源清单导入与试采派工的接口封装：爬虫配置核对来源，采集调度消费接入清单。 */
import { request } from './client'

export type IntakeRow = {
  行号: number
  来源别名: string
  起始地址: string
  页面编码: string
  核对状态: string
  待查原因: string
  原页标题: string
  原清单行: string
  核对记录: { 时间: string; 结果: string; 说明: string }[]
}

export type ImportReceipt = {
  回执编号: string
  导入时间: string
  导入人: string
  随附样本数: number
  清单行: IntakeRow[]
  汇总: { 清单行数: number; 核对通过: number; 待查: number }
  补证记录: { 时间: string; 起始地址: string; 操作人: string; 结果: string }[]
}

export type ReceiptSummary = Omit<ImportReceipt, '清单行'>

export type TrialRequest = {
  试采编号: string
  回执编号: string
  清单行号: number
  来源别名: string
  起始地址: string
  页面编码: string
  原页标题: string
  原清单行: string
  状态: string
  派工时间: string
  操作人: string
}

export type PendingSource = {
  行号: number
  来源别名: string
  起始地址: string
  页面编码: string
  待查原因: string
  原清单行: string
}

export type DispatchResult = {
  回执编号: string
  本次派工: TrialRequest[]
  已受理未重发: TrialRequest[]
  待补证: PendingSource[]
  汇总: { 本次派工: number; 已受理未重发: number; 待补证: number }
}

export type SampleInput = { 起始地址: string; 页面编码: string; 原页内容: string }

async function parseJson<T>(response: Response, fallback: string): Promise<T> {
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error((data as { detail?: string }).detail ?? fallback)
  }
  return data as T
}

export async function importSourceList(
  csvText: string,
  samples: SampleInput[],
  operator: string,
): Promise<{ ok: boolean; message: string; 回执: ImportReceipt }> {
  const response = await request('/api/crawler_config/source-imports', {
    method: 'POST',
    body: JSON.stringify({ csv_text: csvText, samples, operator }),
  })
  return parseJson(response, '来源清单导入失败')
}

export async function listSourceImports(): Promise<{ items: ReceiptSummary[]; total: number }> {
  const response = await request('/api/crawler_config/source-imports')
  return parseJson(response, '导入回执读取失败')
}

export async function getSourceImport(receiptId: string): Promise<{ 回执: ImportReceipt }> {
  const response = await request(`/api/crawler_config/source-imports/${receiptId}`)
  return parseJson(response, '采集接入清单读取失败')
}

export async function supplementSample(
  receiptId: string,
  sample: SampleInput,
  operator: string,
): Promise<{ ok: boolean; message: string }> {
  const response = await request(`/api/crawler_config/source-imports/${receiptId}/samples`, {
    method: 'POST',
    body: JSON.stringify({
      address: sample.起始地址,
      encoding: sample.页面编码,
      content_b64: sample.原页内容,
      operator,
    }),
  })
  return parseJson(response, '补证样本提交失败')
}

export async function dispatchTrial(
  receiptId: string,
  operator: string,
): Promise<{ ok: boolean; message: string } & DispatchResult> {
  const response = await request('/api/crawl_schedule/trial-dispatches', {
    method: 'POST',
    body: JSON.stringify({ receipt_id: receiptId, operator }),
  })
  return parseJson(response, '试采派工失败')
}

export async function listTrialRequests(
  receiptId = '',
): Promise<{ items: TrialRequest[]; total: number }> {
  const query = receiptId ? `?receipt_id=${encodeURIComponent(receiptId)}` : ''
  const response = await request(`/api/crawl_schedule/trial-dispatches${query}`)
  return parseJson(response, '试采请求核查失败')
}

/** 读取本地原页文件为 base64，供随附样本和补证样本使用。 */
export function readFileAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(new Error('本地原页读取失败'))
    reader.onload = () => {
      const result = String(reader.result ?? '')
      resolve(result.includes(',') ? result.slice(result.indexOf(',') + 1) : result)
    }
    reader.readAsDataURL(file)
  })
}
