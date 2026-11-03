"""Check the frozen application in an isolated Chinese path, without Python on PATH."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", type=Path, default=ROOT / "dist/ZuJiChangZheng.exe")
    parser.add_argument("--output", type=Path, default=ROOT / ".artifacts/打包核验")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    exe = output / "足迹长征.exe"
    shutil.copy2(args.exe.resolve(), exe)
    env = os.environ.copy()
    windows = Path(env.get("WINDIR", "C:/Windows"))
    env["PATH"] = f"{windows / 'System32'};{windows}"
    for key in ["PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV", "QT_QPA_PLATFORM"]:
        env.pop(key, None)

    def run(arguments: list[str], log_name: str) -> int:
        with (output / log_name).open("wb") as log:
            process = subprocess.Popen([str(exe), *arguments], cwd=output, env=env,
                                       stdout=log, stderr=log)
            try:
                return process.wait(timeout=45)
            except subprocess.TimeoutExpired:
                # A windowed bootloader can leave its dialog-owning child alive.
                subprocess.run([str(windows / "System32/taskkill.exe"), "/PID",
                                str(process.pid), "/T", "/F"],
                               stdout=log, stderr=log, check=False)
                raise RuntimeError(f"Packaged startup timed out; see {output / log_name}")

    screenshot = output / "01-native-startup.png"
    raw = json.loads((ROOT / "assets/content/nodes.json").read_text(encoding="utf-8"))
    expected_nodes = len(raw["nodes"])
    expected_questions = sum(min(raw.get("quiz_size") or len(node["questions"]), len(node["questions"]))
                             for node in raw["nodes"])
    assert run(["--smoke-check", str(screenshot), "--data-dir", str(output / "默认存档")],
               "native.log") == 0
    normal = json.loads(screenshot.with_suffix(".json").read_text(encoding="utf-8"))
    assert normal["frozen"] and normal["nodes"] == expected_nodes
    assert normal["questions"] == expected_questions
    lesson_image = output / "04-learning-preview.png"
    assert run(["--preview-lesson", "--smoke-check", str(lesson_image), "--data-dir",
                str(output / "学习模板存档")], "lesson.log") == 0
    preview = json.loads(lesson_image.with_suffix(".json").read_text(encoding="utf-8"))
    assert preview["frozen"] and preview["lesson_preview"] and preview["lesson_scenes"] >= 1
    external = output / "外部内容包"
    external.mkdir(exist_ok=True)
    raw["id"] = "external-smoke-test"
    raw["nodes"] = raw["nodes"][:1]
    (external / "nodes.json").write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    custom_image = output / "02-external-content.png"
    assert run(["--content-dir", str(external), "--smoke-check", str(custom_image),
                "--data-dir", str(output / "外部包存档")], "external.log") == 0
    custom = json.loads(custom_image.with_suffix(".json").read_text(encoding="utf-8"))
    assert custom["frozen"] and custom["nodes"] == 1
    assert custom["questions"] == min(raw.get("quiz_size") or len(raw["nodes"][0]["questions"]),
                                      len(raw["nodes"][0]["questions"]))
    invalid_image = output / "03-invalid-content.png"
    assert run(["--content-dir", str(output / "不存在的内容目录"), "--smoke-check",
                str(invalid_image), "--data-dir", str(output / "无效包存档")], "invalid.log") == 1
    assert invalid_image.with_suffix(".error.txt").exists()
    report = {"ok": True, "exe_bytes": exe.stat().st_size,
              "sha256": hashlib.sha256(exe.read_bytes()).hexdigest(),
              "checks": ["frozen native startup", "Chinese executable and directory paths",
                         "PATH without Python", "frozen lesson preview", "external content replacement",
                         "invalid content controlled exit"]}
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
