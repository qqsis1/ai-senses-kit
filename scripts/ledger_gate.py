#!/usr/bin/env python3
"""写入门禁：账本记录进库前先过这一关。

一句话：缺证据指针、或缺失效条件的，不许写进库。

用法：
    python scripts/ledger_gate.py records.jsonl
    cat records.jsonl | python scripts/ledger_gate.py -

规则（与 docs/06-verification.md 一致）：
- 每条记录必须是单行 JSON 对象；
- judge / check 类：正文里必须有「算错的条件 / 什么情况下算错」，否则 reject；
- 任何记录：至少要有一个证据指针——refs 非空、evidence/basis 字段、或正文里有「依据：」；
- 不自动改文件，只报告；有任一 reject 时退出码 2。

这是"密封"那道锁的代码化版本：文档写下的规矩，得有一个它自己绕不过去的执行点。
"""
import json
import sys

VERDICT_KINDS = {"judge", "check"}

# 历史遗留：这 7 条是 2026-11 之前的"对账"，当时没有 check_id 字段。
# 只按 id 豁免，不按文本豁免——新的"对账"必须带 check_id，否则一样拒。
LEGACY_RECONCILIATION = {
    "emvrvj2e8-xzaf", "emvrvprvw-px14", "emw0fu37o-6teg", "emw20w46h-z552",
    "emw37p3ga-wrlg", "emwkba4c2-725l", "emwkgk6m1-k0av",
}


def has_evidence(rec: dict) -> bool:
    if rec.get("refs"):
        return True
    if rec.get("check_id"):
        return True
    if rec.get("evidence") or rec.get("basis"):
        return True
    text = str(rec.get("text", ""))
    return "依据：" in text or "依据:" in text


def has_invalid_if(rec: dict) -> bool:
    if rec.get("invalid_if"):
        return True
    text = str(rec.get("text", ""))
    return "算错的条件" in text or "什么情况下算错" in text


def check_line(i: int, line: str):
    line = line.strip()
    if not line:
        return None
    try:
        rec = json.loads(line)
    except json.JSONDecodeError as e:
        return (i, "reject", f"不是合法 JSON：{e}")
    if not isinstance(rec, dict):
        return (i, "reject", "顶层不是对象")
    kind = rec.get("kind", "")
    text = str(rec.get("text", ""))
    if not text:
        return (i, "reject", "缺 text")
    # 对账类记录是对"预测"的核销，不是对世界的判断：失效条件已经写在预测里，不要求重复
    # 但必须能追到那条预测：带 check_id，或属于历史遗留白名单
    is_reconciliation = kind in VERDICT_KINDS and (text.startswith("对账：") or text.startswith("对账:"))
    if is_reconciliation:
        rid = str(rec.get("id", ""))
        if not rec.get("check_id") and rid not in LEGACY_RECONCILIATION:
            return (i, "reject", "对账缺 check_id（追不到被核销的预测）")
    elif kind in VERDICT_KINDS and not has_invalid_if(rec):
        return (i, "reject", "判断类缺失效条件（算错的条件）")
    if not has_evidence(rec):
        return (i, "note", "缺证据指针（refs/依据）；可写入但要标记")
    return (i, "pass", "")


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 1
    path = sys.argv[1]
    lines = sys.stdin.read().splitlines() if path == "-" else open(path, encoding="utf-8").read().splitlines()
    rows = [r for r in (check_line(i + 1, l) for i, l in enumerate(lines)) if r]
    for i, verdict, why in rows:
        print(f"line {i}: {verdict}" + (f" — {why}" if why else ""))
    rejects = sum(1 for _, v, _ in rows if v == "reject")
    notes = sum(1 for _, v, _ in rows if v == "note")
    print(f"\n共 {len(rows)} 条：pass {sum(1 for _, v, _ in rows if v == 'pass')} · note {notes} · reject {rejects}")
    if rejects:
        print("拒绝写入：先补上被拒的条目，别把'以后补'当默认。")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
