"""pyautogui 唯一合法持有者。

所有 pyautogui 调用包 asyncio.to_thread（避免阻塞 event loop，R4 缓解）。
对应 spec.md FR-018、研究 R5（pyautogui 归属 cap-agent）。
"""
from __future__ import annotations

import asyncio
import io
import time
from typing import Any

from cap_agent.core.exceptions import InvalidActionError


class GUIBackend:
    """pyautogui 操作封装。

    `_ensure_pa` 懒加载，避免无 DISPLAY 时 import 阶段失败；
    单元测试通过 patch 该模块的 gui_backend 单例或上层 router mock 整个对象。
    """

    def __init__(self) -> None:
        self._pa: Any = None

    def _ensure_pa(self) -> Any:
        """懒加载 pyautogui。"""
        if self._pa is None:
            import pyautogui  # 局部 import，避免无 DISPLAY 容器/CI 启动失败

            self._pa = pyautogui
            # 失败时抛异常而非傻等；不引入额外 PAUSE 延迟
            self._pa.FAILSAFE = False
            self._pa.PAUSE = 0
        return self._pa

    async def screenshot(self) -> bytes:
        """截屏，返回 PNG bytes。"""
        return await asyncio.to_thread(self._screenshot_sync)

    def _screenshot_sync(self) -> bytes:
        """同步截屏（在线程池中执行）。"""
        pa = self._ensure_pa()
        img = pa.screenshot()
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    async def execute(self, action: Any) -> dict[str, Any]:
        """执行 16 种动作之一。

        Args:
            action: GUIAction 子类实例（来自 cap_agent.models.actions）。
        """
        return await asyncio.to_thread(self._execute_sync, action)

    def _execute_sync(self, action: Any) -> dict[str, Any]:
        """同步执行（在线程池中）。"""
        pa = self._ensure_pa()
        at = action.action_type

        if at == "click":
            pa.click(action.x, action.y, button=action.button)
        elif at == "dbl_click":
            pa.doubleClick(action.x, action.y)
        elif at == "right_click":
            pa.rightClick(action.x, action.y)
        elif at == "move_to":
            pa.moveTo(action.x, action.y)
        elif at == "move_rel":
            pa.moveRel(action.dx, action.dy)
        elif at == "scroll":
            pa.scroll(action.amount, x=action.x, y=action.y)
        elif at == "drag":
            pa.dragTo(action.x, action.y, duration=action.duration)
        elif at == "typing":
            if action.text.isascii():
                pa.typewrite(action.text)
            else:
                # 非 ASCII 通过剪贴板输入（P1 简化）
                pa.hotkey(*self._type_unicode(action.text))
        elif at == "hotkey":
            pa.hotkey(*action.keys)
        elif at == "key_down":
            pa.keyDown(action.key)
        elif at == "key_up":
            pa.keyUp(action.key)
        elif at == "screenshot":
            # 截屏走 /gui/screenshot 路由；这里返回占位
            pass
        elif at == "wait":
            time.sleep(action.seconds)
        elif at == "locate":
            box = pa.locateOnScreen(action.image_path, confidence=action.confidence)
            return {"ok": True, "found": box is not None, "box": list(box) if box else None}
        elif at == "wait_for":
            try:
                box = pa.locateOnScreen(action.image_path, confidence=0.9)
                return {"ok": True, "found": box is not None}
            except Exception as e:  # noqa: BLE001 — 不让单个动作中断流水
                return {"ok": False, "error": str(e)}
        elif at == "resize":
            # VNC 分辨率调整不在 pyautogui 范围；P1 占位
            return {"ok": False, "error": "resize not implemented in P1"}
        else:  # pragma: no cover - discriminated union 已在路由层过滤
            raise InvalidActionError(f"未知 action_type: {at}")

        return {"ok": True}

    @staticmethod
    def _type_unicode(text: str) -> tuple[str, ...]:
        """非 ASCII 字符通过剪贴板输入（P1 简化）。"""
        import pyperclip

        pyperclip.copy(text)
        return ("ctrl", "v")


# 模块级单例：路由层 import 此对象；测试通过 patch gui_backend 替换
gui_backend = GUIBackend()
