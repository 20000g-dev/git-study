"""기능 이슈 생성 스크립트 (feature-issue 스킬).

gh CLI를 감싸서 아래 작업을 한 번에 처리한다.
  1. gh 로그인 확인
  2. 대상 저장소 확인 (git remote 기준)
  3. 유사 이슈 중복 검색 — 있으면 생성하지 않고 중단 (exit 3)
  4. 고정 한글 라벨 중 없는 것만 생성
  5. 이슈 생성 (본문은 --body-file로 전달)
  6. --worktree 지정 시 이슈 번호 기반 워크트리 생성

사용 예:
  python create_feature_issue.py --title "혼잡도 시간대별 집계 추가" \
      --body-file <임시>/issue_body.md --type 기능 --topic 혼잡도 \
      --slug congestion-hourly --worktree --dry-run

종료 코드: 0 성공 · 1 일반 오류 · 2 gh 미로그인 · 3 유사 이슈 발견 (생성 안 함)
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# 라벨 이름: (색상, 설명). references/labels.md와 동기화할 것.
LABELS = {
    "기능": ("0E8A16", "새 기능 추가"),
    "개선": ("A2EEEF", "기존 기능 개선"),
    "버그": ("D73A4A", "오류 수정"),
    "문서": ("0075CA", "문서 작업"),
    "혼잡도": ("FBCA04", "혼잡도 분석"),
    "OD": ("F9D0C4", "정류장 OD 분석"),
    "환승": ("C5DEF5", "환승 분석"),
    "운임": ("BFD4F2", "운임 분석"),
    "데이터": ("D4C5F9", "데이터 준비·갱신"),
}
TYPE_LABELS = ["기능", "개선", "버그", "문서"]
TOPIC_LABELS = ["혼잡도", "OD", "환승", "운임", "데이터"]

EXIT_ERROR = 1
EXIT_NOT_LOGGED_IN = 2
EXIT_DUPLICATE = 3


def die(message, code=EXIT_ERROR):
    print(f"[오류] {message}", file=sys.stderr)
    sys.exit(code)


def gh(args, check=True):
    """gh 명령 실행. 실패 시 check=True면 예외."""
    return subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=check,
    )


def check_login():
    result = gh(["auth", "status"], check=False)
    if result.returncode != 0:
        print("[중단] gh CLI에 로그인되어 있지 않습니다.", file=sys.stderr)
        print("사용자가 터미널에서 직접 실행하세요: gh auth login", file=sys.stderr)
        sys.exit(EXIT_NOT_LOGGED_IN)


def repo_name():
    result = gh(["repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"])
    return result.stdout.strip()


def existing_labels(repo):
    result = gh(["label", "list", "--repo", repo, "--limit", "200", "--json", "name", "-q", ".[].name"])
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def find_duplicates(repo, title):
    """제목 기준 유사 이슈 검색. 열린 것과 닫힌 것 모두 본다."""
    result = gh([
        "issue", "list", "--repo", repo, "--state", "all", "--limit", "10",
        "--search", f"{title} in:title",
        "--json", "number,title,url,state",
    ])
    return json.loads(result.stdout or "[]")


def create_label_if_missing(repo, name, existing, dry_run):
    if name in existing:
        return
    color, description = LABELS[name]
    if dry_run:
        print(f"  [dry-run] 라벨 생성 예정: {name} (#{color})")
        return
    gh(["label", "create", name, "--repo", repo, "--color", color, "--description", description])
    print(f"  라벨 생성: {name}")


def create_issue(repo, title, body_file, labels):
    args = ["issue", "create", "--repo", repo, "--title", title, "--body-file", str(body_file)]
    for label in labels:
        args += ["--label", label]
    result = gh(args)
    return result.stdout.strip()


def issue_number_from_url(url):
    match = re.search(r"/issues/(\d+)", url)
    if not match:
        die(f"이슈 번호를 URL에서 찾지 못했습니다: {url}")
    return int(match.group(1))


def create_worktree(number, slug):
    toplevel = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout.strip()
    repo_root = Path(toplevel)
    branch = f"feature/{number}-{slug}"
    path = repo_root.parent / f"{repo_root.name}-issue-{number}"

    if path.exists():
        die(f"워크트리 경로가 이미 있습니다: {path}")
    branch_check = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"],
        capture_output=True, text=True,
    )
    if branch_check.returncode == 0:
        die(f"같은 이름의 브랜치가 이미 있습니다: {branch}")

    subprocess.run(
        ["git", "worktree", "add", str(path), "-b", branch, "main"],
        check=True, capture_output=True, text=True, encoding="utf-8",
    )
    return branch, path


def main():
    parser = argparse.ArgumentParser(description="기능 이슈 + 라벨 + 워크트리 생성")
    parser.add_argument("--title", required=True, help="이슈 제목 (한국어)")
    parser.add_argument("--body-file", required=True, type=Path, help="본문 마크다운 파일 (저장소 밖 임시 경로 권장)")
    parser.add_argument("--type", required=True, choices=TYPE_LABELS, help="유형 라벨 (1개)")
    parser.add_argument("--topic", action="append", default=[], choices=TOPIC_LABELS, help="주제 라벨 (0~1개)")
    parser.add_argument("--worktree", action="store_true", help="이슈 생성 후 워크트리 생성")
    parser.add_argument("--slug", help="브랜치 슬러그 (영문 소문자·하이픈). --worktree와 함께 필수")
    parser.add_argument("--dry-run", action="store_true", help="생성 없이 계획만 출력 (중복 검색은 수행)")
    args = parser.parse_args()

    if args.worktree and not args.slug:
        die("--worktree를 쓰려면 --slug가 필요합니다.")
    if args.slug and not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", args.slug):
        die("--slug는 영문 소문자·숫자·하이픈만 허용합니다. 예: congestion-hourly")
    if not args.body_file.is_file():
        die(f"본문 파일이 없습니다: {args.body_file}")
    if len(args.topic) > 1:
        die("주제 라벨은 최대 1개입니다.")

    check_login()
    repo = repo_name()
    print(f"대상 저장소: {repo}")

    duplicates = find_duplicates(repo, args.title)
    if duplicates:
        print("[중단] 유사한 이슈가 이미 있습니다. 새로 만들지 않았습니다:")
        for item in duplicates:
            print(f"  - #{item['number']} ({item['state']}) {item['title']}\n    {item['url']}")
        sys.exit(EXIT_DUPLICATE)

    labels = [args.type, *args.topic]
    existing = existing_labels(repo)
    print(f"제목: {args.title}")
    print(f"라벨: {', '.join(labels)}")

    if args.dry_run:
        print("[dry-run] 이하 작업은 실행하지 않습니다.")
        for name in labels:
            create_label_if_missing(repo, name, existing, dry_run=True)
        print(f"[dry-run] 이슈 생성 예정 → {args.body_file}")
        if args.worktree:
            print(f"[dry-run] 워크트리 예정 → feature/<번호>-{args.slug}")
        return

    for name in labels:
        create_label_if_missing(repo, name, existing, dry_run=False)

    url = create_issue(repo, args.title, args.body_file, labels)
    number = issue_number_from_url(url)
    print(f"이슈 생성 완료: {url}")

    if args.worktree:
        branch, path = create_worktree(number, args.slug)
        print(f"워크트리 생성 완료: {path}")
        print(f"브랜치: {branch} (기준: main)")


if __name__ == "__main__":
    main()
