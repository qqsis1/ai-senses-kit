"""ledger_gate 的门禁规则测试：不读写真实账本。"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ledger_gate  # noqa: E402


def verdict(line_no, rec):
    return ledger_gate.check_line(line_no, json.dumps(rec, ensure_ascii=False))


class GateTest(unittest.TestCase):
    def test_judge_without_invalid_if_rejected(self):
        r = verdict(1, {"kind": "judge", "text": "这个方案可行。", "refs": ["x"]})
        self.assertEqual(r[1], "reject")

    def test_judge_with_invalid_if_passes(self):
        r = verdict(1, {"kind": "judge", "text": "这个方案可行。依据：测试。算错的条件：证据反转。", "refs": ["x"]})
        self.assertEqual(r[1], "pass")

    def test_reconciliation_without_check_id_rejected(self):
        r = verdict(1, {"kind": "judge", "text": "对账：对了。", "refs": ["x"]})
        self.assertEqual(r[1], "reject")

    def test_reconciliation_with_check_id_passes(self):
        r = verdict(1, {"kind": "judge", "text": "对账：对了。", "check_id": "pred-1"})
        self.assertEqual(r[1], "pass")

    def test_legacy_reconciliation_allowed(self):
        legacy = sorted(ledger_gate.LEGACY_RECONCILIATION)[0]
        r = verdict(1, {"id": legacy, "kind": "judge", "text": "对账：对了。", "refs": ["x"]})
        self.assertEqual(r[1], "pass")

    def test_missing_text_rejected(self):
        r = verdict(1, {"kind": "say"})
        self.assertEqual(r[1], "reject")

    def test_bad_json_rejected(self):
        r = ledger_gate.check_line(1, "{not json")
        self.assertEqual(r[1], "reject")


if __name__ == "__main__":
    unittest.main()
