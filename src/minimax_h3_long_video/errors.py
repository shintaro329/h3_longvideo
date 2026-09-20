"""定义项目级异常，避免业务模块依赖 CLI 实现。"""


class ConfigurationError(ValueError):
    """表示 storyboard 或 H3 输入契约不合法。"""


class RuntimeDependencyError(RuntimeError):
    """表示运行时缺少 ffmpeg、Diffusers 或模型依赖。"""

