"""변경 파일을 수집하고 데이터 분석 저장소 기준의 '커밋 후보 그룹'을 제안한다.

사용법:  python collect_changes.py [--repo PATH] [--json]

출력은 어디까지나 *초안*이다. 자동 그룹핑은 경로·파일명 규칙에 의존하므로,
최종 묶음은 diff 내용을 읽고 판단해야 한다 (SKILL.md 참고).
"""
import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path, PurePosixPath

LARGE_BYTES = 10 * 1024 * 1024

SENSITIVE = re.compile(r"(^|/)(\.env(\..*)?|.*\.(pem|key|p12|pfx)|credentials.*|secrets?.*)$", re.I)
JUNK = re.compile(r"(^|/)(__pycache__/|\.ipynb_checkpoints/|\.DS_Store$|Thumbs\.db$|~\$)")
RAW_DATA_EXT = {".xlsx", ".xls", ".parquet", ".feather", ".pkl", ".pickle", ".sav", ".db", ".sqlite"}
CODE_EXT = {".py", ".sql", ".r", ".sh", ".scala"}
DOC_EXT = {".md", ".rst", ".txt"}
DEP_FILES = {"requirements.txt", "pyproject.toml", "environment.yml", "environment.yaml",
             "poetry.lock", "pipfile", "pipfile.lock", "setup.py", "setup.cfg"}
CONFIG_FILES = {".gitignore", ".gitattributes", ".editorconfig", ".pre-commit-config.yaml"}
RESULT_DIRS = {"results", "result", "output", "outputs", "reports", "report", "figures", "charts"}
DATA_DIRS = {"data", "datasets", "raw", "reference"}
STOP_TOKENS = {"analyze", "analysis", "make", "build", "run", "test", "get", "read", "summary",
               "top", "top10", "matrix", "data", "dummy", "result", "results", "report", "plot"}


def git(repo, *args):
    out = subprocess.run(["git", "-C", repo, "-c", "core.quotepath=off", *args],
                         capture_output=True, check=True)
    return out.stdout.decode("utf-8", "replace")


def classify(path):
    p = PurePosixPath(path)
    name, ext, parts = p.name.lower(), p.suffix.lower(), [x.lower() for x in p.parts[:-1]]
    if JUNK.search(path):
        return "junk"
    if name in DEP_FILES:
        return "deps"
    if name in CONFIG_FILES or parts[:1] == [".github"] or parts[:1] == [".claude"]:
        return "config"
    if parts[:1] == ["tests"] or name.startswith("test_") or name.endswith("_test.py"):
        return "test"
    if ext == ".ipynb":
        return "notebook"
    if ext in DOC_EXT or parts[:1] == ["docs"]:
        return "doc"
    if parts and parts[0] in RESULT_DIRS:
        return "report-or-result" if ext in {".png", ".jpg", ".svg", ".html", ".pdf"} else "result"
    if parts and parts[0] in DATA_DIRS or ext in RAW_DATA_EXT:
        return "data"
    if ext in CODE_EXT:
        return "code"
    if ext in {".csv", ".json", ".tsv"}:
        return "result"
    return "other"


def topic_tokens(path):
    stem = PurePosixPath(path).stem.lower()
    return {t for t in re.split(r"[^a-z0-9]+", stem) if t and t not in STOP_TOKENS}


def changed_files(repo):
    raw = subprocess.run(["git", "-C", repo, "status", "--porcelain=v1", "-z", "-uall"],
                         capture_output=True, check=True).stdout.decode("utf-8", "replace")
    entries, items = raw.split("\0"), []
    i = 0
    while i < len(entries):
        e = entries[i]
        i += 1
        if len(e) < 4:
            continue
        xy, path = e[:2], e[3:]
        if xy[0] in "RC":          # rename/copy: 다음 토큰이 원래 경로
            i += 1
        items.append({"path": path, "status": xy})
    return items


def numstat(repo):
    stats = {}
    for args in (["diff", "--numstat"], ["diff", "--cached", "--numstat"]):
        for line in git(repo, *args).splitlines():
            a, d, path = line.split("\t", 2)
            add, dele = (0 if a == "-" else int(a)), (0 if d == "-" else int(d))
            old = stats.get(path, (0, 0))
            stats[path] = (old[0] + add, old[1] + dele)
    return stats


def file_size(repo, path):
    try:
        return (Path(repo) / path).stat().st_size
    except OSError:
        return 0


def group(items):
    """code 파일의 주제 토큰을 키로 삼아 result/data/doc/test를 같은 그룹으로 끌어온다."""
    groups = defaultdict(list)
    anchors = [(topic_tokens(i["path"]), i) for i in items if i["kind"] == "code"]
    for it in items:
        k = it["kind"]
        if k in {"deps", "config", "junk"}:
            groups[f"_{k}"].append(it)
            continue
        key = None
        toks = topic_tokens(it["path"])
        if k == "code":
            key = "topic:" + (sorted(toks)[0] if toks else PurePosixPath(it["path"]).stem)
        elif k in {"result", "report-or-result", "test", "notebook", "data", "doc"}:
            for atoks, anchor in anchors:
                if atoks & toks:
                    key = "topic:" + sorted(atoks)[0]
                    break
        if key is None:
            key = {"doc": "_doc", "data": "_data", "notebook": "_notebook"}.get(k, f"_{k}")
        groups[key].append(it)
    return groups


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    items = changed_files(args.repo)
    if not items:
        print("변경 사항 없음 (working tree clean)")
        return
    stats = numstat(args.repo)
    warnings = []
    for it in items:
        it["kind"] = classify(it["path"])
        it["added"], it["deleted"] = stats.get(it["path"], (None, None))
        size = file_size(args.repo, it["path"])
        it["size"] = size
        if it["kind"] == "junk":
            warnings.append(f"임시/캐시 파일: {it['path']} (커밋 제외 권장)")
        if SENSITIVE.search(it["path"]):
            warnings.append(f"자격 증명 의심 파일: {it['path']} (커밋 금지)")
        if size >= LARGE_BYTES:
            warnings.append(f"대용량({size / 1e6:.1f}MB): {it['path']} (원본 데이터면 .gitignore 고려)")
        if it["kind"] == "notebook":
            warnings.append(f"노트북: {it['path']} (실행 출력에 데이터/개인정보가 남았는지 확인)")
        if it["kind"] == "data" and it["status"].strip() in {"??", "A"}:
            warnings.append(f"데이터 파일 신규: {it['path']} (원본/개인정보/재생성 가능 여부 확인)")

    groups = group(items)
    if args.json:
        print(json.dumps({"groups": groups, "warnings": warnings}, ensure_ascii=False, indent=2))
        return

    print(f"변경 파일 {len(items)}개 → 후보 그룹 {len(groups)}개 (초안, diff를 읽고 조정할 것)\n")
    for gi, (key, files) in enumerate(sorted(groups.items()), 1):
        print(f"[그룹 {gi}] {key}")
        for f in files:
            delta = "" if f["added"] is None else f"  +{f['added']}/-{f['deleted']}"
            print(f"   {f['status']} {f['kind']:<16} {f['path']}{delta}")
        print()
    if warnings:
        print("주의:")
        for w in dict.fromkeys(warnings):
            print(f"  - {w}")


if __name__ == "__main__":
    main()
