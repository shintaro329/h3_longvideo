#!/usr/bin/env bash
# 使用最小 CPU 检查验证目录结构、窗口调度和 storyboard 契约。
set -euo pipefail

cd "$(dirname "$0")/.."
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m minimax_h3_long_video \
  configs/storyboard.example.json \
  --dry-run \
  --output-dir outputs/h3_60s_dry_run
