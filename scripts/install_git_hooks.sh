#!/usr/bin/env bash
# Cài pre-commit hook chặn commit file .env / mosquitto passwd (lớp phòng vệ 2 ngoài .gitignore).
# Chạy 1 lần tại thư mục app_service: bash scripts/install_git_hooks.sh
set -euo pipefail

HOOK_DIR="$(git rev-parse --git-path hooks)"
mkdir -p "$HOOK_DIR"
cat > "$HOOK_DIR/pre-commit" <<'HOOK'
#!/usr/bin/env bash
# Chặn secret lọt vào commit.
blocked=$(git diff --cached --name-only | grep -E '(^|/)\.env($|\.)|(^|/)mosquitto/passwd$' || true)
if [ -n "$blocked" ]; then
  echo "❌ Từ chối commit — phát hiện file chứa secret:"
  echo "$blocked"
  echo "Nếu chắc chắn cần commit (hiếm), dùng: git commit --no-verify"
  exit 1
fi
HOOK
chmod +x "$HOOK_DIR/pre-commit"
echo "Đã cài pre-commit hook tại $HOOK_DIR/pre-commit"
