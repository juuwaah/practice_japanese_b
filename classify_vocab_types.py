# JLPT語彙スプレッドシートのType判定・レベル間重複削除スクリプト
#
# 使い方:
#   ./venv/bin/python classify_vocab_types.py --levels N5              # N5のみType判定
#   ./venv/bin/python classify_vocab_types.py --levels all --dedup     # 全レベル判定+重複削除
#   --dry-run を付けるとシートには書き込まず、結果CSVだけ出力する
#
# 実行のたびに全タブをCSVでバックアップしてから書き込む。

import argparse
import csv
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import anthropic
import gspread

from claude_helper import ask_claude_json

SPREADSHEET_ID = "17HIhkhevNTtHiZPyDDmCXAn0Rxy_OFaCT9UGF4HaOM4"
CREDENTIALS = "japaneseapp-466108-327bc89dfc8e.json"
LEVELS = ["N5", "N4", "N3", "N2", "N1"]  # 難易度が低い順（重複時は先のレベルを残す）
BATCH_SIZE = 50
MAX_WORKERS = 2
BACKUP_DIR = "sheet_backups"

TYPE_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "type": {
                        "type": "string",
                        "enum": ["noun", "verb", "adjective", "other"],
                    },
                    "confident": {"type": "boolean"},
                    "meaning": {"type": "string"},
                },
                "required": ["index", "type", "confident", "meaning"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}

PROMPT_HEADER = """あなたは日本語語彙データベースを整備する日本語教育の専門家です。
以下のJLPT語彙リストの各語について品詞を判定してください。

品詞は次の4種類のみです:
- "noun": 名詞。する動詞の語幹（勉強、感激 など）も、リストに「〜する」が付かない形で載っていれば noun
- "verb": 動詞。「〜する」付きで載っている場合（感激する など）も verb
- "adjective": い形容詞・な形容詞（きれい、静か なども adjective）
- "other": 副詞・接続詞・連体詞・感動詞・助数詞・慣用表現など上記以外すべて（あいかわらず、たとえば など）

英語のMeaningも判断材料にしてください（"to 〜"なら動詞の可能性が高い等）。
複数の品詞で同じくらい使われる・どうしても判定に迷う場合のみ confident を false にしてください。

さらに各語の meaning（英語の意味）を改善して返してください:
- 動詞は他動詞/自動詞が区別できる書き方にする: 他動詞は "to open something" / "to praise someone" のように something/someone を付け、自動詞は "to open" のように付けない
- 主要な意味が複数あればカンマ区切りで2〜4個まで: "to ask, to listen to"
- 誤字・不自然な英語・途中で切れている意味は修正する。固有名詞以外は小文字で統一
- 既存のMeaningが上記を満たしていれば、そのまま変えずに返す

各語を {index}. 漢字表記 / 読み / 英語の意味 の形式で示します。
全ての語について index を対応させて判定を返してください。

単語リスト:
"""


def open_spreadsheet():
    gc = gspread.service_account(filename=CREDENTIALS)
    return gc.open_by_key(SPREADSHEET_ID)


def load_tab(ws):
    """タブの全値を読み、ヘッダーとデータ行(行番号付き)を返す"""
    values = ws.get_all_values()
    if not values:
        raise RuntimeError(f"{ws.title}: シートが空です")
    header = [h.strip() for h in values[0]]  # N1タブの「Error 」など末尾スペース対策
    for col in ("Kanji", "Word", "Meaning", "Type", "Error"):
        if col not in header:
            raise RuntimeError(f"{ws.title}: ヘッダーに {col} 列がありません: {header}")
    rows = []  # (行番号(1始まり), dict)
    for i, raw in enumerate(values[1:], start=2):
        row = {header[j]: (raw[j] if j < len(raw) else "") for j in range(len(header))}
        rows.append((i, row))
    return header, rows


def backup_all_tabs(ss, run_dir):
    os.makedirs(run_dir, exist_ok=True)
    for level in LEVELS:
        ws = ss.worksheet(level)
        values = ws.get_all_values()
        path = os.path.join(run_dir, f"{level}.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(values)
        print(f"  バックアップ: {path} ({len(values)}行)")


def find_duplicates(ss):
    """N5→N1の順に走査し、既出の(Kanji, Word)が再登場した行を level→[行番号] で返す"""
    seen = {}
    duplicates = {}  # level -> list of (row_number, kanji, word, first_seen_level)
    for level in LEVELS:
        ws = ss.worksheet(level)
        _, rows = load_tab(ws)
        for row_num, row in rows:
            kanji = row["Kanji"].strip()
            word = row["Word"].strip()
            if not kanji and not word:
                continue
            key = (kanji, word)
            if key in seen:
                duplicates.setdefault(level, []).append((row_num, kanji, word, seen[key]))
            else:
                seen[key] = level
    return duplicates


def delete_rows(ss, ws, row_numbers):
    """行番号のリストをまとめて削除（降順に連続区間をまとめて1回のbatch_updateで）"""
    if not row_numbers:
        return
    nums = sorted(set(row_numbers), reverse=True)
    ranges = []  # (start, end) 1始まり・両端含む
    start = end = nums[0]
    for n in nums[1:]:
        if n == start - 1:
            start = n
        else:
            ranges.append((start, end))
            start = end = n
    ranges.append((start, end))
    requests = [
        {
            "deleteDimension": {
                "range": {
                    "sheetId": ws.id,
                    "dimension": "ROWS",
                    "startIndex": s - 1,  # 0始まり
                    "endIndex": e,        # 終端は含まない
                }
            }
        }
        for s, e in ranges
    ]
    ss.batch_update({"requests": requests})


def classify_batch(batch):
    """batch: [(index, kanji, word, meaning)] → {index: (type, confident, meaning)}"""
    lines = [f"{idx}. {kanji or '（なし）'} / {word or '（なし）'} / {meaning or '（意味未記入）'}"
             for idx, kanji, word, meaning in batch]
    prompt = PROMPT_HEADER + "\n".join(lines)
    last_err = None
    for attempt in range(4):
        try:
            result = ask_claude_json(prompt, TYPE_SCHEMA, max_tokens=8000)
            return {item["index"]: (item["type"], item["confident"], item["meaning"].strip())
                    for item in result["items"]}
        except (anthropic.RateLimitError, anthropic.APIConnectionError) as e:
            last_err = e
            wait = 15 * (attempt + 1)
            print(f"  レート制限/接続エラー、{wait}秒待って再試行 ({attempt + 1}/4)")
            time.sleep(wait)
        except anthropic.APIError as e:
            last_err = e
            if getattr(e, "status_code", None) == 529:
                time.sleep(15 * (attempt + 1))
            else:
                raise
    raise last_err


def classify_level(ss, level, dry_run, report_writer):
    ws = ss.worksheet(level)
    header, rows = load_tab(ws)
    col_type = header.index("Type") + 1
    col_error = header.index("Error") + 1
    col_meaning = header.index("Meaning") + 1

    targets = []  # (index=行番号, kanji, word, meaning, old_type)
    for row_num, row in rows:
        kanji = row["Kanji"].strip()
        word = row["Word"].strip()
        if not kanji and not word:
            continue
        targets.append((row_num, kanji, word, row["Meaning"].strip(), row["Type"].strip()))

    print(f"{level}: {len(targets)}語を判定します（{BATCH_SIZE}語×{-(-len(targets) // BATCH_SIZE)}バッチ）")

    batches = [targets[i:i + BATCH_SIZE] for i in range(0, len(targets), BATCH_SIZE)]
    results = {}  # 行番号 -> (type, confident)
    done = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {
            pool.submit(classify_batch, [(t[0], t[1], t[2], t[3]) for t in batch]): batch
            for batch in batches
        }
        for future in as_completed(futures):
            results.update(future.result())
            done += 1
            print(f"  {level}: バッチ {done}/{len(batches)} 完了")

    # 書き込み用の列データを組み立て（対象外の行は元の値を保持）
    last_row = rows[-1][0] if rows else 1
    type_col_values = []
    error_col_values = []
    meaning_col_values = []
    counts = {"noun": 0, "verb": 0, "adjective": 0, "other": 0, "error": 0, "meaning_changed": 0}
    for row_num, row in rows:
        new_type = row.get("Type", "")
        new_error = row.get("Error", "")
        new_meaning = row.get("Meaning", "")
        if results.get(row_num):
            new_type, confident, new_meaning = results[row_num]
            if not new_meaning:  # 空で返ってきたら元の意味を保持
                new_meaning = row.get("Meaning", "")
            new_error = "" if confident else "1"
            counts[new_type] += 1
            if not confident:
                counts["error"] += 1
            if new_meaning != row.get("Meaning", "").strip():
                counts["meaning_changed"] += 1
        elif any(t[0] == row_num for t in targets):
            # APIが該当indexを返さなかった行 → Error=1
            new_error = "1"
            counts["error"] += 1
        report_writer.writerow([level, row["Kanji"], row["Word"],
                                row["Meaning"], new_meaning,
                                row["Type"], new_type, new_error])
        type_col_values.append([new_type])
        error_col_values.append([new_error])
        meaning_col_values.append([new_meaning])

    if not dry_run and rows:
        a1_type = gspread.utils.rowcol_to_a1(2, col_type)[:-1]  # 列文字のみ
        a1_err = gspread.utils.rowcol_to_a1(2, col_error)[:-1]
        a1_mean = gspread.utils.rowcol_to_a1(2, col_meaning)[:-1]
        ws.update(values=type_col_values, range_name=f"{a1_type}2:{a1_type}{last_row}")
        ws.update(values=error_col_values, range_name=f"{a1_err}2:{a1_err}{last_row}")
        ws.update(values=meaning_col_values, range_name=f"{a1_mean}2:{a1_mean}{last_row}")

    print(f"{level}: 完了 — noun {counts['noun']} / verb {counts['verb']} / "
          f"adjective {counts['adjective']} / other {counts['other']} / "
          f"Meaning変更 {counts['meaning_changed']} / 要確認(Error=1) {counts['error']}")
    return counts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--levels", required=True,
                        help="判定するレベル（カンマ区切り、例: N5,N4）または all")
    parser.add_argument("--dedup", action="store_true", help="レベル間の重複行を削除する")
    parser.add_argument("--dry-run", action="store_true", help="シートに書き込まない")
    args = parser.parse_args()

    levels = LEVELS if args.levels == "all" else [l.strip() for l in args.levels.split(",")]
    for l in levels:
        if l not in LEVELS:
            sys.exit(f"不明なレベル: {l}")

    ss = open_spreadsheet()
    run_dir = os.path.join(BACKUP_DIR, datetime.now().strftime("%Y%m%d_%H%M%S"))

    print("=== バックアップ ===")
    backup_all_tabs(ss, run_dir)

    if args.dedup:
        print("=== レベル間の重複チェック ===")
        duplicates = find_duplicates(ss)
        dup_path = os.path.join(run_dir, "deleted_duplicates.csv")
        with open(dup_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["level", "row", "Kanji", "Word", "kept_in_level"])
            for level in LEVELS:
                for row_num, kanji, word, first in duplicates.get(level, []):
                    w.writerow([level, row_num, kanji, word, first])
        total = sum(len(v) for v in duplicates.values())
        print(f"重複 {total}件（詳細: {dup_path}）")
        if not args.dry_run:
            for level in LEVELS:
                rows_to_delete = [r for r, *_ in duplicates.get(level, [])]
                if rows_to_delete:
                    delete_rows(ss, ss.worksheet(level), rows_to_delete)
                    print(f"  {level}: {len(rows_to_delete)}行を削除")

    print("=== Type判定 ===")
    report_path = os.path.join(run_dir, "classification_report.csv")
    with open(report_path, "w", newline="", encoding="utf-8") as f:
        report_writer = csv.writer(f)
        report_writer.writerow(["level", "Kanji", "Word", "old_meaning", "new_meaning",
                                "old_type", "new_type", "error"])
        for level in levels:
            classify_level(ss, level, args.dry_run, report_writer)

    print(f"\nレポート: {report_path}")
    if args.dry_run:
        print("（dry-run: シートには書き込んでいません）")


if __name__ == "__main__":
    main()
