#!/usr/bin/env bash
# push-github.sh — 一键同步到 GitHub（临时分支方式，不污染本地历史）
#
# 原理：
#   1. 创建临时分支 _github_push_tmp（从当前 HEAD）
#   2. 在临时分支上 filter-branch 改写身份 + 清理 Co-Authored-By
#   3. force push 临时分支 → github/master
#   4. 删除临时分支
#   本地主分支 hash 完全不变，不影响与 origin 的同步关系
#
# 配置：
#   git config push-github.name  'your-github-username'
#   git config push-github.email 'your@gmail.com'
set -e

GITHUB_NAME=$(git config push-github.name 2>/dev/null || echo "")
GITHUB_EMAIL=$(git config push-github.email 2>/dev/null || echo "")

if [[ -z "$GITHUB_NAME" || -z "$GITHUB_EMAIL" ]]; then
  echo "❌ 请先配置 GitHub 身份："
  echo "   git config push-github.name  'your-username'"
  echo "   git config push-github.email 'your@gmail.com'"
  exit 1
fi

BRANCH=$(git rev-parse --abbrev-ref HEAD)
LOCAL_HEAD=$(git rev-parse HEAD)
TMP_BRANCH="_github_push_tmp"

echo "📦 当前分支: $BRANCH ($LOCAL_HEAD)"

# 清理可能残留的临时分支和 filter-branch 备份
git branch -D "$TMP_BRANCH" 2>/dev/null || true
rm -rf .git/refs/original

# Stash unstaged changes (filter-branch refuses to run with dirty worktree)
STASHED=false
if ! git diff --quiet 2>/dev/null; then
  git stash --quiet
  STASHED=true
fi

# 1. 创建临时分支（不切换，保持在当前分支）
git branch "$TMP_BRANCH" HEAD

# 2. 在临时分支上 filter-branch 改写身份（不影响主分支）
echo "🔄 切换临时分支为 GitHub 身份 ($GITHUB_NAME)..."
FILTER_BRANCH_SQUELCH_WARNING=1 git filter-branch -f \
  --env-filter "
export GIT_AUTHOR_NAME=\"$GITHUB_NAME\"
export GIT_AUTHOR_EMAIL=\"$GITHUB_EMAIL\"
export GIT_COMMITTER_NAME=\"$GITHUB_NAME\"
export GIT_COMMITTER_EMAIL=\"$GITHUB_EMAIL\"
" \
  --msg-filter "sed '/^Co-Authored-By:.*noreply@anthropic\.com/Id; /^Co-authored-by:.*noreply@anthropic\.com/Id'" \
  -- refs/heads/$TMP_BRANCH > /dev/null 2>&1

# 3. 推送临时分支到 github/master
echo "🚀 推送到 GitHub..."
git push --force github "$TMP_BRANCH:$BRANCH"

# 4. 删除临时分支（本地主分支未被修改）
git branch -D "$TMP_BRANCH" 2>/dev/null || true
rm -rf .git/refs/original

# Restore stashed changes
if [ "$STASHED" = true ]; then
  git stash pop --quiet
fi

echo "✅ 完成！GitHub 已同步，本地 $BRANCH 历史未改动"
