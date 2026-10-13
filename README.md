# git-study

Git 기본 사용법을 정리한 학습용 저장소입니다.

## 1. Git이란?

Git은 파일의 변경 이력을 기록하고 관리하는 **분산 버전 관리 시스템**입니다. 언제든 과거 시점으로 돌아갈 수 있고, 여러 사람이 같은 프로젝트를 동시에 작업할 수 있습니다.

## 2. 기본 용어

| 용어 | 설명 |
| --- | --- |
| 저장소(Repository) | 프로젝트와 그 변경 이력을 담은 폴더 (`.git` 폴더 포함) |
| 작업 디렉터리(Working Directory) | 실제로 파일을 편집하는 공간 |
| 스테이징 영역(Staging Area) | 다음 커밋에 포함할 변경을 모아두는 공간 |
| 커밋(Commit) | 스테이징된 변경을 하나의 이력으로 저장한 것 |
| 브랜치(Branch) | 독립적으로 작업하는 커밋의 흐름 |
| 원격 저장소(Remote) | GitHub 등 네트워크에 있는 저장소 (보통 `origin`) |
| HEAD | 현재 작업 중인 위치(브랜치 또는 커밋) |

## 3. 초기 설정

커밋할 때 사용할 이름과 이메일을 한 번 설정합니다.

```bash
git config --global user.name "본인 이름"
git config --global user.email "example@example.com"
```

설정 확인:

```bash
git config --list
```

## 4. 저장소 만들기 / 가져오기

```bash
# 현재 폴더를 새 저장소로 초기화
git init

# 원격 저장소를 로컬로 복제
git clone https://github.com/사용자명/저장소명.git
```

## 5. 기본 작업 흐름

```bash
# 1) 현재 상태 확인
git status

# 2) 변경 내용 확인
git diff

# 3) 스테이징 (커밋에 포함할 파일 선택)
git add 파일명      # 특정 파일
git add .           # 모든 변경

# 4) 커밋
git commit -m "커밋 메시지"

# 5) 원격 저장소에 올리기
git push origin main
```

### 좋은 커밋 메시지 예시

```
docs: README에 git 사용법 추가
fix: 로그인 시 비밀번호 검증 오류 수정
feat: 사용자 프로필 페이지 추가
```

## 6. 이력 조회

```bash
git log                     # 전체 커밋 이력
git log --oneline           # 한 줄로 간단히
git log --oneline --graph   # 브랜치 흐름을 그래프로
git show 커밋해시            # 특정 커밋의 변경 내용
```

## 7. 브랜치

```bash
git branch                  # 브랜치 목록
git branch 새브랜치명        # 새 브랜치 생성
git switch 브랜치명          # 브랜치 전환
git switch -c 새브랜치명     # 생성과 전환을 한 번에
git branch -d 브랜치명       # 병합된 브랜치 삭제
```

## 8. 병합(Merge)과 리베이스(Rebase)

```bash
# main에 feature 브랜치의 작업을 합치기
git switch main
git merge feature

# feature 브랜치를 최신 main 위로 옮기기
git switch feature
git rebase main
```

- **merge**: 두 브랜치의 이력을 합치는 커밋을 새로 만듭니다. 이력이 그대로 보존됩니다.
- **rebase**: 내 커밋을 다른 브랜치의 끝으로 옮겨 이력을 일직선으로 만듭니다. 이미 공유한 커밋에는 사용하지 않는 것이 좋습니다.

## 9. 충돌(Conflict) 해결

같은 부분을 두 브랜치에서 수정하면 충돌이 발생합니다.

1. `git status`로 충돌 파일을 확인합니다.
2. 파일 안의 `<<<<<<<`, `=======`, `>>>>>>>` 표시를 보고 남길 내용을 직접 고칩니다.
3. 수정한 파일을 스테이징하고 커밋합니다.

```bash
git add 충돌파일
git commit
```

## 10. 원격 저장소와 동기화

```bash
git remote -v               # 원격 저장소 주소 확인
git fetch origin            # 원격 변경 내용만 가져오기 (병합 안 함)
git pull origin main        # 가져오기 + 병합
git push origin 브랜치명     # 로컬 브랜치를 원격에 올리기
```

## 11. 되돌리기

```bash
# 작업 중인 파일의 변경 취소 (스테이징 전)
git restore 파일명

# 스테이징 취소
git restore --staged 파일명

# 마지막 커밋 메시지 수정 (아직 push 전에만 권장)
git commit --amend

# 특정 커밋의 변경을 되돌리는 새 커밋 만들기 (이력 보존, 공유 저장소에 안전)
git revert 커밋해시

# 브랜치 위치를 과거 커밋으로 되돌리기 (이력이 사라지므로 주의)
git reset --soft HEAD~1     # 커밋만 취소, 변경은 스테이징 상태로 유지
git reset --hard 커밋해시    # 작업 내용까지 모두 삭제 (주의)
```

> ⚠️ `git reset --hard`는 커밋되지 않은 변경을 영구적으로 지웁니다. 실행 전에 한 번 더 확인하세요.

## 12. 임시 저장 (Stash)

아직 커밋하기 애매한 작업을 잠시 치워둘 때 사용합니다.

```bash
git stash                   # 현재 변경을 임시 저장
git stash list              # 임시 저장 목록
git stash pop               # 가장 최근 임시 저장을 꺼내 적용
```

## 13. 자주 쓰는 명령 요약

| 목적 | 명령 |
| --- | --- |
| 상태 확인 | `git status` |
| 변경 내용 보기 | `git diff` |
| 스테이징 | `git add 파일명` |
| 커밋 | `git commit -m "메시지"` |
| 이력 보기 | `git log --oneline` |
| 브랜치 생성·전환 | `git switch -c 이름` |
| 병합 | `git merge 브랜치명` |
| 원격 올리기 | `git push origin 브랜치명` |
| 원격 내려받기 | `git pull origin 브랜치명` |
| 임시 저장 | `git stash` |

## 14. 참고 자료

- [Pro Git 책 (한국어)](https://git-scm.com/book/ko/v2)
- [Git 공식 문서](https://git-scm.com/doc)
- [GitHub Docs](https://docs.github.com)
