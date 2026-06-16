"""P1 Base 镜像构建与启动 e2e 验证。

对应任务 T011。
"""
import subprocess
import pytest

BASE_IMAGES = [
    ("base-os", "echo ok"),
    ("base-python312", "python3 --version"),
    ("base-node24", "node --version"),
    ("base-vnc", "Xvnc -version 2>&1 | head -1"),
]


@pytest.mark.parametrize("image,cmd", BASE_IMAGES)
def test_base_image_runnable(image: str, cmd: str) -> None:
    """每个 base 镜像可 docker run 并执行命令。"""
    result = subprocess.run(
        ["docker", "run", "--rm", image, "sh", "-c", cmd],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, f"{image} 启动失败: {result.stderr}"
