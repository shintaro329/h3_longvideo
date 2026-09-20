# MiniMax H3 长视频生成

本仓库提供一条基于 MiniMax H3 Ref2VA 的推理编排 pipeline：输入 60 秒 storyboard 和参考资产，按 H3 支持的窗口生成多个片段，再合成为一个 60 秒 MP4 视频。

pipeline 会校验每次 H3 请求的窗口和参考资产限制，通过上一窗口的尾部片段传递视觉连续性，并使用 `ffmpeg` 完成片段拼接。

## 功能

- 校验 60 秒 storyboard、shot 时间轴、参考资产和 Ref2VA 约束。
- 按 24 FPS 将时间轴切分为 5 个 H3 合法窗口：每个窗口 345 帧、14.375 秒，窗口间 overlap 为 2.96875 秒。
- 按窗口选择持久资产和时间范围内的图片、视频、音频资产。
- 检测视频参考是否带音轨，并使 H3 prompt 中的 `<Audio N>` 编号与参考顺序一致。
- 每个窗口生成 continuation tail，作为下一个窗口的视觉参考。
- 使用 `ffmpeg` 对窗口进行交叉淡化，输出 `final_60s.mp4`。
- 通过 manifest fingerprint 支持中断恢复和结果复用。
- 提供 dry-run、CPU-only 契约测试和 CI 工作流。

## 处理流程

```text
storyboard.json
      │
      ▼
校验输入并规划 H3 窗口
      │
      ├── 选择当前窗口参考资产
      ├── 生成窗口 prompt
      └── 调用 H3 Ref2VA 生成窗口
                    │
                    ├── 保存窗口 MP4
                    └── 抽取 continuation tail
                              │
                              ▼
                    使用 ffmpeg 拼接窗口
                              │
                              ▼
                         final_60s.mp4
```

## 环境要求

- Python 3.10 或更高版本。
- dry-run 和测试只需要 Python 标准库。
- 真实生成需要 PyTorch、支持 MiniMax H3 的 Diffusers、`ffmpeg` 和 `ffprobe`。
- 需要能够加载 `MiniMaxAI/MiniMax-H3` 或其他兼容 H3 的模型环境。

仓库不包含模型权重和媒体资产。默认模型为 `MiniMaxAI/MiniMax-H3`，使用前请阅读上游模型许可证。

## 安装

```bash
python -m venv .venv
source .venv/bin/activate

# CPU 检查和测试
pip install -e ".[dev]"

# 真实生成所需依赖
pip install -e ".[runtime]"
```

真实运行前检查外部工具：

```bash
ffmpeg -version
ffprobe -version
```

## 快速使用

### Dry-run

dry-run 会校验 storyboard、生成窗口计划和 prompt，不加载模型权重，也不读取真实媒体文件：

```bash
PYTHONPATH=src python -m minimax_h3_long_video \
  configs/storyboard.example.json \
  --dry-run \
  --output-dir outputs/h3_60s_dry_run
```

### 生成视频

复制 `configs/storyboard.example.json`，将资产路径替换为真实文件，然后运行：

```bash
PYTHONPATH=src python -m minimax_h3_long_video \
  configs/storyboard.json \
  --output-dir outputs/my_60s_run \
  --model-id MiniMaxAI/MiniMax-H3 \
  --device cuda \
  --dtype bfloat16
```

安装后也可以使用命令行入口：

```bash
h3-long-video configs/storyboard.json \
  --output-dir outputs/my_60s_run \
  --device cuda \
  --dtype bfloat16
```

### 恢复中断任务

使用相同的 storyboard、资产、模型参数、窗口参数和 seed：

```bash
PYTHONPATH=src python -m minimax_h3_long_video \
  configs/storyboard.json \
  --output-dir outputs/my_60s_run \
  --device cuda \
  --dtype bfloat16 \
  --resume
```

`--resume` 要求输出目录中已有 `manifest.json`。只有当 storyboard、生成参数、窗口计划和资产路径元信息的 fingerprint 一致时，已有窗口才会被复用；fingerprint 不一致会终止运行，避免混合不同输入产生的结果。复用前会重新校验窗口媒体，continuation tail 会从当前窗口重新生成。

### 只生成窗口、不拼接最终视频

```bash
PYTHONPATH=src python -m minimax_h3_long_video \
  configs/storyboard.json \
  --output-dir outputs/chunks_only \
  --device cuda \
  --dtype bfloat16 \
  --skip-stitch
```

## Storyboard 格式

完整模板见 [`configs/storyboard.example.json`](configs/storyboard.example.json)。顶层字段如下：

| 字段 | 说明 |
|---|---|
| `duration_s` | 必须为 `60`。 |
| `fps` | 必须为 `24`。 |
| `global_prompt` | 全局画面、动作和风格描述。 |
| `continuity` | 可选的角色、环境、镜头、光照、色彩和音频连续性描述。 |
| `assets` | 窗口生成使用的参考资产。 |
| `shots` | 按顺序无间隙覆盖 `[0, 60)` 的 shot 区间。 |
| `master_audio` | 可选的最终音轨；设置后，最终拼接使用该音轨替代窗口生成音频。 |

每个资产的基本结构如下：

```json
{
  "id": "hero",
  "kind": "image",
  "path": "../data/examples/assets/hero.png",
  "role": "persistent",
  "description": "the main character reference"
}
```

支持的 `kind` 为 `image`、`video` 和 `audio`。`transient` 资产必须同时提供 `start_s` 和 `end_s`，只有时间范围相交的窗口会使用该资产。每个 shot 通过 `asset_ids` 指定当前镜头使用的参考资产。

参考资产校验遵循 H3 Ref2VA 约束：

- 每次请求最多 9 个图片参考、3 个视频参考、3 个音频参考，总参考数最多 12 个。
- 每个视频参考必须为 2–15.2 秒，视频参考总时长不得超过 15.2 秒；每个视频会在模型调用前校验。
- 每个显式音频参考必须为 2–15 秒，显式音频总时长不得超过 15 秒。
- 显式音频不能作为请求中的唯一参考。

## 命令行参数

| 参数 | 默认值 | 说明 |
|---|---:|---|
| `--output-dir` | `outputs/h3_60s` | 保存 prompt、窗口、tail、manifest 和最终视频的目录。 |
| `--model-id` | `MiniMaxAI/MiniMax-H3` | H3 模型标识。 |
| `--device` | `cuda` | Torch 设备。 |
| `--dtype` | `bfloat16` | 可选 `bfloat16`、`float16`、`float32`。 |
| `--height` | `768` | 输出高度，必须是 32 的倍数。 |
| `--width` | `1344` | 输出宽度，必须是 32 的倍数。 |
| `--chunk-seconds` | `14.375` | H3 窗口时长。 |
| `--chunks` | `5` | 窗口数量。 |
| `--seed` | `20260920` | 基础 seed，第 `i` 个窗口使用 `seed + i`。 |
| `--dry-run` | 关闭 | 只校验和规划，不执行模型推理。 |
| `--resume` | 关闭 | 复用兼容的已完成窗口。 |
| `--skip-stitch` | 关闭 | 生成窗口后停止，不拼接最终视频。 |

## 输出文件

一次完整运行通常生成：

```text
outputs/my_60s_run/
├── manifest.json
├── chunk_plan.json
├── chunk_01.prompt.txt ... chunk_05.prompt.txt
├── chunk_01.mp4 ... chunk_05.mp4
├── tail_01.mp4 ... tail_04.mp4
└── final_60s.mp4
```

`manifest.json` 保存运行 fingerprint、窗口状态、媒体元信息和最终输出状态。生成媒体和运行目录已配置为 Git 忽略项。

## 代码对应关系

| 路径 | 功能 |
|---|---|
| `src/minimax_h3_long_video/cli.py` | 解析命令行参数并启动运行。 |
| `src/minimax_h3_long_video/runner.py` | 编排输入校验、窗口规划、生成、恢复和拼接。 |
| `src/minimax_h3_long_video/storyboard.py` | 加载和校验 storyboard JSON。 |
| `src/minimax_h3_long_video/schemas.py` | 定义 storyboard、资产、shot 和窗口数据结构。 |
| `src/minimax_h3_long_video/scheduler.py` | 对齐帧数并生成 H3 窗口计划。 |
| `src/minimax_h3_long_video/assets.py` | 为每个窗口选择持久资产和时间范围资产。 |
| `src/minimax_h3_long_video/prompting.py` | 生成确定性的 prompt 和参考标签。 |
| `src/minimax_h3_long_video/references.py` | 校验并构造 H3 Ref2VA 参考对象。 |
| `src/minimax_h3_long_video/media_probe.py` | 读取媒体元信息并校验时长和音轨。 |
| `src/minimax_h3_long_video/h3_adapter.py` | 加载 Diffusers 并执行单个 H3 生成请求。 |
| `src/minimax_h3_long_video/media_edit.py` | 使用 ffmpeg 抽取 tail 和拼接 MP4。 |
| `src/minimax_h3_long_video/manifest.py` | 读取并原子写入运行状态。 |
| `tests/` | 覆盖窗口调度、storyboard 校验和运行契约的 CPU-only 测试。 |

## 验证

```bash
python -m compileall -q src tests
PYTHONPATH=src python -m unittest discover -s tests -v
./scripts/check_dry_run.sh
```

## 相关项目

- [MiniMax H3](https://github.com/MiniMax-AI/MiniMax-H3)
- [Diffusers MiniMax H3 pipeline](https://huggingface.co/docs/diffusers/main/en/api/pipelines/minimax_h3)
- [VDN-Minimax-H3](https://github.com/OpenVDN/vdn-minimax-h3)
