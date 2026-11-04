"""Import the team's chapters JSON embedded in a DOCX, using only the standard library."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import xml.etree.ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.content import JsonContentRepository


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("document", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "assets/content/nodes.json")
    parser.add_argument("--report", type=Path, default=ROOT / "docs/question-bank-import.md")
    args = parser.parse_args()
    with ZipFile(args.document) as archive:
        xml = ET.fromstring(archive.read("word/document.xml"))
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    text = "\n".join("".join(t.text or "" for t in p.findall(".//w:t", namespace))
                     for p in xml.findall(".//w:p", namespace))
    decoder = json.JSONDecoder()
    incoming, _ = decoder.raw_decode(text[text.index("{"):])
    chapters = incoming["chapters"]
    raw = json.loads(args.output.read_text(encoding="utf-8-sig"))
    nodes = {n["id"]: n for n in raw["nodes"]}
    chapter_ids = [chapter["chapterId"] for chapter in chapters]
    if len(set(chapter_ids)) != len(chapter_ids) or set(chapter_ids) != set(nodes):
        raise ValueError("文档章节必须与当前项目一一对应")
    corrections = []
    for chapter in chapters:
        if len(chapter["questions"]) < 10:
            raise ValueError(f"{chapter['chapterId']} 不足10题")
        for q in chapter["questions"]:
            # Only repair evident transcription errors, never silently change an answer.
            if q["id"] == "xiangjiang-basic-result":
                before = q["prompt"]
                q["prompt"] = before.replace(" directly ", "直接")
                if before != q["prompt"]:
                    corrections.append(f"`{q['id']}`：题干中的 directly 改为“直接”。")
            for before, after in [("3万余人足", "3万余人是"), ("30万余人足", "30万余人是"),
                                  ("8.6万余人足", "8.6万余人是")]:
                if before in q["explanation"]:
                    q["explanation"] = q["explanation"].replace(before, after)
                    corrections.append(f"`{q['id']}`：解析中的“{before}”改为“{after}”。")
        nodes[chapter["chapterId"]]["questions"] = chapter["questions"]
    raw.update(version="0.2.0", quiz_size=10, review_status="draft")
    # Validate the full merged content before replacing the project's content file.
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "nodes.json").write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
        JsonContentRepository(Path(tmp)).load()
    args.output.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    singles = [q for c in chapters for q in c["questions"] if q["type"] == "single_choice"]
    first_answers = sum(q["answer"] == [q["options"][0]["id"]] for q in singles)
    report = ["# 题库导入与待核验记录", "", f"来源：用户提供的《{args.document.name}》。",
              f"源文件SHA256：`{hashlib.sha256(args.document.read_bytes()).hexdigest()}`。", "",
              "按文档的chapters / chapterId映射到nodes.json的nodes / id，仅替换题目并启用quiz_size=10。保留原章节资料来源占位，review_status保持draft。文档未提供逐题来源或核验记录，本次仅做结构校验和明显错字修正，不代表完成史实审核。", "",
              "| 章节 | ID | 单选 | 多选 | 合计 |", "|---|---|---:|---:|---:|"]
    for c in chapters:
        counts = Counter(q["type"] for q in c["questions"])
        report.append(f"| {c['title']} | `{c['chapterId']}` | {counts['single_choice']} | {counts['multiple_choice']} | {len(c['questions'])} |")
    report += ["", f"合计{sum(len(c['questions']) for c in chapters)}题；{len(singles)}道单选中{first_answers}道答案在首项。经用户确认，运行时同时打乱选项，按稳定选项ID判断答案。每章抽10题，同一轮不重复，题目及选项顺序随存档保存；复习沿用本轮，重新出发清空后重抽。少于10题的外部小内容包使用全部题目。", "",
               "## 明显文字修正", "", *[f"- {c}" for c in corrections], "",
               "## 需要题库同学复核", "",
               "- 全部题目补充官方页面链接或出版物版次、页码，记录核验人和日期。当前导入不新增或臆造来源。",
               "- `departure-time-start`题干同时出现“开始实行战略转移”与“踏上征途”，答案选10月中旬，而解析提到10月10日；请明确是问渡河出发还是行动开始。",
               "- 四渡赤水范围：原章节时间写1935年1月至3月，文档必讲内容及部分解析写1月至5月；请区分四次渡河行动与更广的战役范围，统一口径。涉及`chishui-end`、`chishui-comprehension-deception`、`river-crossings-comprehension-sequence`等。",
               "- `reunion-comprehension-different-armies`以红二十五军“没有参加”为答案，而选项又说已并入红一方面军；请明确是否指独立建制，避免与人员实际参加产生歧义。",
               "- 湘江战役前后兵力、敌军人数、会师日期和部队编成、典型故事及引语均需要逐项核对，不能把文档本身当作史料出处。",
               "- 学习过场仍保留占位，下面的必讲清单仅整理供文案负责人使用，不自动写入正式学习内容。需要继续核对是否覆盖每道候选题（如于都河水系、红二方面军编成等），避免随机抽到未讲知识。", "",
               "## 文档附带的必讲知识点（原文待核验）", ""]
    for c in chapters:
        report += [f"### {c['title']} `{c['chapterId']}`", "",
                   *[f"- {point}" for point in c.get("mustTeach", [])], ""]
    args.report.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"Imported {sum(len(c['questions']) for c in chapters)} questions; review status: draft")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
