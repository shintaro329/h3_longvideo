# MiniMax H3 长视频生成 Pipeline

本仓库维护一条基于 MiniMax H3 Ref2VA 的 60 秒视频编排 baseline：输入完整 storyboard 和参考资产，按 H3 合法窗口顺序生成，再合成为 60 秒视频。

当前 Diffusers 集成会校验 H3 VAE 的 `17n+5` 帧网格，因此使用最大安全长度 345 帧，即 14.375 秒。五个窗口采用 2.96875 秒 overlap：

```text
5 × 14.375 - 4 × 2.96875 = 60 秒
```

本项目是可恢复的窗口编排 pipeline，不是原生单次 60 秒 H3 模型；不修改 H3 Base 权重、MM-RoPE、VAE 或 Attention 实现。

## 快速开始

干跑只校验 storyboard、帧数网格、资产选择、prompt 和时间轴，不加载模型权重：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

PYTHONPATH=src python -m minimax_h3_long_video \
  configs/storyboard.example.json \
  --dry-run \
  --output-dir outputs/h3_60s_dry_run
```

真实生成需要安装运行时依赖，并确保 `ffmpeg`、`ffprobe` 在 `PATH` 中：

```bash
pip install -e ".[runtime]"

PYTHONPATH=src python -m minimax_h3_long_video \
  configs/storyboard.json \
  --output-dir outputs/my_60s_run \
  --device cuda \
  --dtype bfloat16 \
  --resume
```

示例配置中的资产路径是占位路径。真实生成前应替换为实际文件。模型权重、生成视频和私有数据不得提交到 Git。

## 环境要求与验证

- Python 3.10 或更高版本。
- dry-run 和契约测试不需要 GPU、模型权重或真实媒体资产。
- 真实生成需要兼容的 PyTorch/Diffusers 环境，并确保 `ffmpeg`、`ffprobe` 在 `PATH` 中。
- 默认模型为 `MiniMaxAI/MiniMax-H3`；使用或再分发前应阅读上游模型许可证。

在仓库根目录执行 CPU-only 检查：

```bash
python -m compileall -q src tests
PYTHONPATH=src python -m unittest discover -s tests -v
./scripts/check_dry_run.sh
```

## Storyboard 契约与 resume 行为

当前 baseline 要求 `duration_s=60`、`fps=24`。所有 shot 必须无间隙覆盖完整时间轴，资产路径相对于 storyboard 文件解析。资产类型可以是 `image`、`video` 或 `audio`；显式 Ref2VA 音频不能作为唯一参考，每个显式音频时长必须为 2–15 秒，显式音频总时长不得超过 15 秒。

`--resume` 只有在已有 manifest 的 fingerprint 与 storyboard、生成配置、窗口计划和资产元信息一致时才会复用已完成窗口。fingerprint 不一致会直接终止，避免混用不兼容产物。每个窗口成功生成后都会从当前窗口重新生成 continuation tail；只有发现缺失窗口需要推理时才加载 H3 pipeline。

## 目录职责

```text
code/
├── README.md                         # 英文入口
├── README.zh-CN.md                   # 中文入口
├── pyproject.toml                    # 包和依赖配置
├── configs/                          # 可复现的公开配置示例
├── src/minimax_h3_long_video/        # 运行时 Python 包
│   ├── assets.py                     # 持久资产和窗口局部资产选择
│   ├── cli.py                        # 仅负责命令行参数
│   ├── constants.py                  # H3 契约和项目默认值
│   ├── errors.py                     # 项目级异常
│   ├── h3_adapter.py                 # 延迟加载 Diffusers 和单窗口生成
│   ├── manifest.py                   # 可恢复 manifest 的原子写入
│   ├── media_edit.py                 # ffmpeg 尾部抽取和视频合成
│   ├── media_probe.py                # ffprobe 元数据和媒体校验
│   ├── prompting.py                  # 确定性的 H3 full-reference prompt
│   ├── references.py                 # Ref2VA 参考对象和数量限制
│   ├── runner.py                     # 端到端流程编排
│   ├── schemas.py                    # storyboard 和窗口数据结构
│   ├── scheduler.py                  # VAE 帧数对齐和窗口规划
│   └── storyboard.py                  # JSON 加载和契约校验
├── tests/                            # CPU-only 契约测试
├── docs/                             # 架构和维护说明
├── data/                             # 数据契约和未来数据集预留
├── training/                         # post-training/LoRA 预留
├── scripts/                          # 可复现的维护入口
└── outputs/                          # 本地生成结果，Git 忽略
```

`CHANGELOG.md` 记录仓库变更，`CONTRIBUTING.md` 定义维护规则，`.github/workflows/ci.yml` 在 push 和 pull request 时自动执行 CPU-only 编译及契约测试。

## Python 文件规则

每个 Python 文件只承担一个明确的核心职责。Python 文件名、函数名、类名、变量名全部使用英文；注释和 docstring 使用中文。跨模块功能通过 `import` 调用，不在下游文件复制实现。

重型 torch、Diffusers 和模型加载只位于 H3 adapter 相关模块，因而 storyboard 解析、窗口调度和 CPU-only 测试不需要 GPU 或模型下载。

## 后续维护预留

`data/` 预留原始视频、storyboard、latent cache、数据索引和 train/eval split 的契约；`training/` 预留冻结 H3 Base 的 continuation LoRA、数据预处理、训练配置和评估入口。本次只提供目录和接口边界，不伪造尚未验证的训练实现。

后续 post-training 应继续复用当前 `ChunkSpec`、参考资产顺序、storyboard schema 和 manifest schema，避免训练链路与推理链路产生隐式协议分叉。

## 上游边界

实现遵循 [MiniMax H3](https://github.com/MiniMax-AI/MiniMax-H3) 和 [Diffusers H3](https://huggingface.co/docs/diffusers/main/en/api/pipelines/minimax_h3) 的公开接口。H3 权重和模型许可证仍属于上游，不能将权重、密钥、私有生成视频或复制的上游源码提交到本仓库。目录设计参考 [VDN-Minimax-H3](https://github.com/OpenVDN/vdn-minimax-h3) 的 `src / configs / docs / scripts / training` 分层方式，但不复制其实现和权重。
