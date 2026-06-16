"""16 种 pyautogui 桌面动作 pydantic 模型。

通过 action_type 字段做 discriminated union 分发。对应 spec.md FR-018、
data-model.md。
"""
from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


class _BaseAction(BaseModel):
    """所有 action 的基类，含 action_type 标识。"""


class ClickAction(_BaseAction):
    """鼠标点击（含按键 left/right/middle，默认 left）。"""

    action_type: Literal["click"]
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    button: Literal["left", "right", "middle"] = "left"


class DblClickAction(_BaseAction):
    """双击。"""

    action_type: Literal["dbl_click"]
    x: int = Field(ge=0)
    y: int = Field(ge=0)


class RightClickAction(_BaseAction):
    """右键点击。"""

    action_type: Literal["right_click"]
    x: int = Field(ge=0)
    y: int = Field(ge=0)


class MoveToAction(_BaseAction):
    """绝对坐标移动。"""

    action_type: Literal["move_to"]
    x: int = Field(ge=0)
    y: int = Field(ge=0)


class MoveRelAction(_BaseAction):
    """相对坐标移动。"""

    action_type: Literal["move_rel"]
    dx: int
    dy: int


class ScrollAction(_BaseAction):
    """滚轮（amount 正负代表方向，x/y 可选锚点）。"""

    action_type: Literal["scroll"]
    amount: int
    x: int | None = None
    y: int | None = None


class DragAction(_BaseAction):
    """拖拽到 (x,y)，duration 秒。"""

    action_type: Literal["drag"]
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    duration: float = Field(default=0.5, ge=0)


class TypingAction(_BaseAction):
    """输入文本。"""

    action_type: Literal["typing"]
    text: str


class HotkeyAction(_BaseAction):
    """组合键，如 ["ctrl","c"]。"""

    action_type: Literal["hotkey"]
    keys: list[str]


class KeyDownAction(_BaseAction):
    """按下键。"""

    action_type: Literal["key_down"]
    key: str


class KeyUpAction(_BaseAction):
    """松开键。"""

    action_type: Literal["key_up"]
    key: str


class ScreenshotAction(_BaseAction):
    """占位：截屏走 /gui/screenshot。"""

    action_type: Literal["screenshot"]


class WaitAction(_BaseAction):
    """等待 seconds 秒。"""

    action_type: Literal["wait"]
    seconds: float = Field(ge=0)


class LocateAction(_BaseAction):
    """在屏幕上定位图像。"""

    action_type: Literal["locate"]
    image_path: str
    confidence: float = Field(default=0.9, ge=0, le=1)


class WaitForAction(_BaseAction):
    """等待图像出现，最长 timeout 秒。"""

    action_type: Literal["wait_for"]
    image_path: str
    timeout: float = Field(default=10.0, ge=0)


class ResizeAction(_BaseAction):
    """调整 VNC 分辨率（P1 占位）。"""

    action_type: Literal["resize"]
    width: int = Field(ge=1)
    height: int = Field(ge=1)


GUIAction = Annotated[
    Union[
        ClickAction, DblClickAction, RightClickAction, MoveToAction, MoveRelAction,
        ScrollAction, DragAction, TypingAction, HotkeyAction, KeyDownAction,
        KeyUpAction, ScreenshotAction, WaitAction, LocateAction, WaitForAction,
        ResizeAction,
    ],
    Field(discriminator="action_type"),
]
