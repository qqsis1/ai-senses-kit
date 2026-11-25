// dsh-bili-kb —— 本地 B 站知识库
// 定位：给刷 B 站加一本"自己的笔记本"。先查库，命中就少读；读完把梗概写回来。
// 边界：梗概只是索引，不是"看过原片"的证据；每条带来源与时间。
// 不依赖 @deepseek-ai/dsh-tools（profile 不装 optional peer），直接注册普通工具定义。
import { find, get, add, stats, formatFind } from './lib/kb-store.mjs'

export const name = 'dsh-bili-kb'
export const inject = ['tools']

const textOut = {
  schema: { type: 'object', properties: { text: { type: 'string' } }, required: ['text'], additionalProperties: false },
  render: (_args, value) => [{ type: 'text', text: String(value?.text ?? '') }],
}

export function apply(ctx) {
  const tool = (spec) => ctx.tools.register({ ...spec, output: textOut })

  tool({
    name: 'kb_find',
    description: '在本地 B 站知识库里按主题找看过的视频（返回 BV、标题、主题、梗概、来源）。**先查这里，再决定要不要花 token 读原片**。命中不代表看过；引用时必须注明来自知识库。',
    parameters: {
      type: 'object',
      properties: {
        query: { type: 'string', description: '主题或关键词，比如“镜头语言 分屏 对比”' },
        limit: { type: 'number', description: '最多返回几条，默认 5' },
      },
      required: ['query'],
      additionalProperties: false,
    },
    async execute(args) {
      const hits = find(args.query, Math.min(Math.max(Number(args.limit) || 5, 1), 10))
      return { text: formatFind(hits) }
    },
  })

  tool({
    name: 'kb_get',
    description: '按 BV 号从本地知识库取一条完整记录（含分段摘要、证据字段）。',
    parameters: { type: 'object', properties: { bvid: { type: 'string', description: 'BV 号' } }, required: ['bvid'], additionalProperties: false },
    async execute(args) {
      const e = get(args.bvid)
      return { text: e ? JSON.stringify(e, null, 2) : `本地库里没有 ${args.bvid}` }
    },
  })

  tool({
    name: 'kb_add',
    description: '把刚读过的视频写进本地知识库。必填 bvid、summary；建议填 title/up/duration/topics/segments/evidence。evidence 写明来源（字幕/扫描报告/画面）与覆盖程度（full/partial）。',
    parameters: {
      type: 'object',
      properties: {
        bvid: { type: 'string' },
        title: { type: 'string' },
        up: { type: 'string' },
        duration: { type: 'string' },
        topics: { type: 'array', items: { type: 'string' } },
        summary: { type: 'string', description: '100–250 字，写清内容、做法与结论' },
        segments: {
          type: 'array',
          items: {
            type: 'object',
            properties: { start: { type: 'number' }, end: { type: ['number', 'null'] }, title: { type: 'string' }, summary: { type: 'string' } },
            required: ['title'],
          },
        },
        evidence: {
          type: 'object',
          properties: { source: { type: 'string' }, coverage: { type: 'string' }, at: { type: 'string' }, watcher: { type: 'string' } },
          required: ['source', 'coverage'],
        },
      },
      required: ['bvid', 'summary'],
      additionalProperties: false,
    },
    async execute(args) {
      const r = add(args)
      return { text: `写入 ${r.added} 条；库内共 ${r.total} 条。` }
    },
  })

  tool({
    name: 'kb_stats',
    description: '看本地知识库有多少条、多少条有分段摘要、覆盖了哪些主题。',
    parameters: { type: 'object', properties: {}, additionalProperties: false },
    async execute() {
      const s = stats()
      return { text: `条目 ${s.total}；有分段摘要 ${s.withSegments}；主题：${s.topics.join('、') || '（无）'}\n最新：${s.latest.map(x => `${x.bvid} ${x.title || ''}`).join(' | ')}` }
    },
  })
}
