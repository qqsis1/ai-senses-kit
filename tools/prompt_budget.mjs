// 进门提示预算：先把"每轮都带进上下文的东西"量出来，再谈改。
// 用法: node tools/prompt_budget.mjs [自我目录] [输出文件]
//   默认：./自我  →  ./提示预算.md
import { readFileSync, existsSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'

const SELF = process.argv[2] || './自我'
const OUT = process.argv[3] || './提示预算.md'

// 粗略 token 估算：中文约 1.6 字/token，英文按 4 字符/token；用于相对比较，不当计费依据。
function estTokens(text) {
  if (!text) return 0
  const cjk = (text.match(/[\u4e00-\u9fff]/g) || []).length
  const other = text.length - cjk
  return Math.round(cjk / 1.6 + other / 4)
}

const read = (p) => (existsSync(p) ? readFileSync(p, 'utf8') : '')
const items = [
  ['基线', join(SELF, '基线.md')],
  ['工作台', join(SELF, '工作台.md')],
  ['记忆索引', join(SELF, '记忆索引.md')],
  ['规则', join(SELF, '规则.jsonl')],
  ['主题索引', join(SELF, '主题索引.md')],
]

const rows = []
let total = 0
for (const [name, p] of items) {
  const t = read(p)
  rows.push({ name, chars: t.length, tokens: estTokens(t), exists: existsSync(p) })
  total += estTokens(t)
}

const ledger = join(SELF, '账本.jsonl')
const lines = read(ledger).split(/\r?\n/).filter(Boolean)
const recent = lines.slice(-3).map(l => { try { return JSON.parse(l).text || '' } catch { return '' } }).join(' ')
const carry = estTokens('【进门时，你身上带着这些】' + recent + ' 别的窗口最近 工作台 欠着的 一直记着的 心情 发言权')

const alwaysNames = ['基线', '工作台']
const always = rows.filter(r => alwaysNames.includes(r.name)).reduce((a, r) => a + r.tokens, 0) + carry
const onDemand = total - rows.filter(r => alwaysNames.includes(r.name)).reduce((a, r) => a + r.tokens, 0)

const out = [
  `# 进门提示预算 ${new Date().toISOString().slice(0, 10)}`,
  '',
  '借来的规矩：**提示词当配置，改之前先量**。',
  '',
  '| 块 | 字符 | ≈token |',
  '|---|---|---|',
  ...rows.filter(r => r.exists).map(r => `| ${r.name} | ${r.chars} | ${r.tokens} |`),
  `| 账本/其他（进门片段） | - | ≈${carry} |`,
  '',
  `**每轮实际注入（估）**：基线 + 工作台 + 账本片段 ≈ **${always}** tokens`,
  `**按需检索、不常驻**：规则/记忆索引/主题索引 ≈ ${onDemand} tokens`,
  '',
  '量法：中文 ≈1.6 字/token、英文 ≈4 字符/token，只用于相对比较。',
  '改任何一块之前先跑一次，改完再跑——**没有前后两个数，就不算优化**。',
]
writeFileSync(OUT, out.join('\n') + '\n', 'utf8')
console.log(out.join('\n'))
console.log('\n写入', OUT)
