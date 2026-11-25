// 本地知识库存储：默认放在插件目录下的 .bili-kb/videos.jsonl，可用 BILI_KB_DIR 指到别处。
// 设计原则：梗概是索引，不是"看过原片"的证据；每条都带来源与时间。
import { readFileSync, appendFileSync, existsSync, mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = dirname(fileURLToPath(import.meta.url))
export const KB_DIR = process.env.BILI_KB_DIR || join(HERE, '..', '.bili-kb')
export const KB_FILE = join(KB_DIR, 'videos.jsonl')

export function load() {
  if (!existsSync(KB_FILE)) return new Map()
  const map = new Map()
  for (const line of readFileSync(KB_FILE, 'utf8').split(/\r?\n/)) {
    if (!line.trim()) continue
    try {
      const e = JSON.parse(line)
      if (e && e.bvid) map.set(e.bvid, e)
    } catch { /* 坏行跳过，不阻塞 */ }
  }
  return map
}

export function tokens(s) {
  const t = String(s || '').toLowerCase()
  const out = []
  for (const w of t.split(/[^0-9a-z\u4e00-\u9fff]+/).filter(Boolean)) {
    if (/^[a-z0-9]+$/.test(w)) { out.push(w); continue }
    for (let i = 0; i < w.length - 1; i++) out.push(w.slice(i, i + 2))
  }
  return [...new Set(out)]
}

export function score(entry, qTokens) {
  const set = new Set(tokens([entry.title, entry.up, entry.summary, (entry.topics || []).join(' '),
    (entry.segments || []).map(s => `${s.title || ''} ${s.summary || ''}`).join(' ')].join(' ')))
  let hit = 0
  for (const t of qTokens) if (set.has(t)) hit++
  return qTokens.length ? hit / qTokens.length : 0
}

export function find(query, limit = 5) {
  const qt = tokens(query)
  return [...load().values()]
    .map(e => ({ e, s: score(e, qt) }))
    .filter(x => x.s > 0)
    .sort((a, b) => b.s - a.s)
    .slice(0, limit)
}

export function get(bvid) { return load().get(String(bvid || '').trim()) || null }

export function add(entries) {
  const list = Array.isArray(entries) ? entries : [entries]
  const map = load()
  const now = new Date().toISOString()
  mkdirSync(KB_DIR, { recursive: true })
  let n = 0
  for (const e of list) {
    if (!e || !e.bvid) continue
    const prev = map.get(e.bvid) || {}
    const merged = { ...prev, ...e, addedAt: prev.addedAt || now, updatedAt: now }
    appendFileSync(KB_FILE, JSON.stringify(merged) + '\n', 'utf8')
    map.set(e.bvid, merged)
    n++
  }
  return { added: n, total: map.size }
}

export function stats() {
  const arr = [...load().values()]
  const topics = [...new Set(arr.flatMap(e => e.topics || []))]
  return {
    total: arr.length,
    withSegments: arr.filter(e => (e.segments || []).length).length,
    topics: topics.slice(0, 20),
    latest: arr.sort((a, b) => String(b.updatedAt || '').localeCompare(String(a.updatedAt || ''))).slice(0, 5)
      .map(e => ({ bvid: e.bvid, title: e.title })),
  }
}

export function formatFind(hits) {
  if (!hits.length) return '本地库没有命中。可以先去刷一轮，读完再用 kb_add 写回来。'
  return hits.map(({ e, s }) => {
    const ev = e.evidence ? `${e.evidence.source}/${e.evidence.coverage} @ ${e.evidence.at}` : '（无证据字段）'
    const segs = (e.segments || []).length ? `\n  分段: ${e.segments.map(x => `${x.start ?? '?'}-${x.end ?? '?'} ${x.title || ''}`).join(' | ').slice(0, 400)}` : ''
    return `[${(s * 100).toFixed(0)}%] ${e.bvid} ${e.title || ''}（${e.up || '?'} · ${e.duration || '?'}）\n  主题: ${(e.topics || []).join('、') || '—'}\n  梗概: ${String(e.summary || '').slice(0, 500)}\n  证据: ${ev}${segs}`
  }).join('\n\n')
}
