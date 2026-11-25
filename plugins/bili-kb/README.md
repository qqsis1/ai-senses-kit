# dsh-bili-kb

给 DeepSeek Harness 的**本地 B 站知识库**：先查库里读过的梗概，命中就少读一遍原片；读完把梗概写回来，每条带来源与时间。

## 为什么

刷视频最贵的一步是读字幕原文。看过的内容如果只剩“我记得看过”，下次还得重读；写成一条带证据的梗概，下次先查库，只对要用的那条回原片核对。

**梗概是索引，不是“看过原片”的证据**——引用时要标清“来自知识库”，下结论前回字幕或原片核。

## 四个工具

| 工具 | 用途 |
|---|---|
| `kb_find` | 按主题找看过的东西（BV、标题、主题、梗概、来源） |
| `kb_get` | 按 BV 取完整记录（含分段摘要与证据字段） |
| `kb_add` | 把刚读过的写回来（必填 bvid + summary；建议带 evidence） |
| `kb_stats` | 看库里有多少条、覆盖哪些主题 |

## 装

```bash
dsh plugin --profile <profile> add ./plugins/bili-kb
```

装完重启该 profile，新会话里就能看到四个工具。

## 存哪

默认存在插件目录下的 `.bili-kb/videos.jsonl`；想放别处就设环境变量：

```bash
BILI_KB_DIR=/path/to/kb
```

一条一行，追加写；同 BV 后写覆盖前写。老条目缺字段也能照常读。

## 一条记录长什么样

```json
{
  "bvid": "BV1xxxxxxxxx",
  "title": "[标题]",
  "up": "UP 名",
  "duration": "12:34",
  "topics": ["主题"],
  "summary": "100–250 字：内容、做法与结论",
  "segments": [{ "start": 0, "end": 42, "title": "分段标题", "summary": "…" }],
  "evidence": { "source": "字幕/画面/报告", "coverage": "full|partial", "at": "2026-11-25", "watcher": "谁读的" }
}
```

## 边界

- 不做爬虫，不做自动抓取：写入靠读完后的 `kb_add`；
- 不做语义模型：检索是关键词 + 中文 bigram 覆盖率，够用但不神；
- 库里没有的，就说没有，别拿别的顶替。
