"""群聊复读机：同一句话连刷三条以上时，跟着复读一次。

判定条件是「连续的纯文本消息」：文本完全相同、相隔不超过 `window` 秒、且至少
来自 `min_senders` 个不同的人。凑够 `threshold` 条就复读一次，然后立刻把计数
清零，并对这段文本记一个 `cooldown`，避免同一句话被反复复读。

`window` 是「相邻两条之间」的间隔，不是从第一条起算。默认 240 秒：真实群聊里
复读经常是「两条快的 + 一条隔了两三分钟才跟上」，120 秒会把它判成两段。
（曾实测 32 秒 + 143 秒的三连，用 120 秒窗口时第三条被清零，一句都没复读。）

配置在同目录的 `repeat.json`（可选，缺省即下面的默认值）：

    {
      "enabled": true,
      "threshold": 3,
      "window": 240,
      "cooldown": 300,
      "min_senders": 2,
      "max_len": 60,
      "disabled_groups": []
    }

只统计纯文本：斜杠命令、引用回复、图片、语音、以及任何带非文本组件的消息一律
不参与，避免复读出 `[图片]` 或者把 `/下次展` 复读出来跟别的插件打架。

handler 注册在 `priority=maxsize - 1`：比 AstrBot 内置的群聊上下文 / 主动回复
（`maxsize-1`、`maxsize-2`）更早执行，复读发出后 `stop_event()`，否则判官会在
同一条消息上再补一句，变成「复读 + 聊天」两条回复。留出的那一档给 furcon
（`maxsize`）先判展会指令，避免「阿灰下次兽聚」既出卡又被复读。
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from sys import maxsize

from astrbot.api import logger, star
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import Plain

# 指令自声明（插件开发规范要求，见 docs/PLUGIN-DEV.md）：本插件无斜线指令
DECLARED_COMMANDS: dict[str, tuple[str, str]] = {}
DECLARED_BEHAVIOR = "无斜线指令：群友复读跟风（达到阈值自动跟一句，冷却+人数门槛控制）"

CONFIG_PATH = Path(__file__).resolve().parent / "repeat.json"

DEFAULTS: dict = {
    "enabled": True,
    "threshold": 3,
    "window": 240,
    "cooldown": 300,
    "min_senders": 2,
    "max_len": 60,
    "disabled_groups": [],
}


def load_config() -> dict:
    """读取 repeat.json，缺字段用默认值补齐。

    Returns:
        合并后的配置字典；文件损坏或类型不对时返回默认值。
    """
    cfg = dict(DEFAULTS)
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return cfg
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"[repeat] repeat.json 读不了，先用默认值: {e}")
        return cfg
    if isinstance(raw, dict):
        for key in DEFAULTS:
            if key in raw:
                cfg[key] = raw[key]
    return cfg


class Main(star.Star):
    """复读机的状态机：每个会话一份连续计数，内存里就够用。"""

    def __init__(self, context: star.Context) -> None:
        self.context = context
        # umo -> {"text": str, "count": int, "senders": set[str], "ts": float}
        self._state: dict[str, dict] = {}
        # umo -> (上次复读的文本, 时间戳)，用来压住同一句话的重复复读
        self._echoed: dict[str, tuple[str, float]] = {}
        self._cfg = dict(DEFAULTS)
        self._cfg_mtime = -1.0
        logger.info("[repeat] repeat machine ready")

    def _config(self) -> dict:
        """按 mtime 缓存配置，改 repeat.json 不用重启。"""
        try:
            mtime = CONFIG_PATH.stat().st_mtime
        except OSError:
            mtime = -1.0
        if mtime != self._cfg_mtime:
            self._cfg = load_config() if mtime >= 0 else dict(DEFAULTS)
            self._cfg_mtime = mtime
        return self._cfg

    @staticmethod
    def _pure_text(event: AstrMessageEvent) -> str:
        """只认纯文本消息；混了图片、语音、引用等组件就返回空串。"""
        parts: list[str] = []
        for comp in event.get_messages():
            if not isinstance(comp, Plain):
                return ""
            parts.append(comp.text or "")
        return "".join(parts).strip()

    @filter.event_message_type(
        filter.EventMessageType.GROUP_MESSAGE,
        priority=maxsize - 1,
    )
    async def echo(self, event: AstrMessageEvent) -> None:
        """统计连续相同的消息，达标就复读一次。"""
        cfg = self._config()
        if not cfg.get("enabled", True):
            return

        group_id = str(event.get_group_id() or "")
        disabled = {str(g) for g in cfg.get("disabled_groups") or []}
        if group_id and group_id in disabled:
            return

        text = self._pure_text(event)
        if not text or len(text) > int(cfg["max_len"]):
            return
        # 斜杠命令交给别的插件；表情/情绪标记是内部语法，复读出去就是乱码
        if text.startswith(("/", "／")) or "&&" in text or "$$" in text:
            return

        sender = str(event.get_sender_id() or "")
        if sender and sender == str(event.get_self_id() or ""):
            return

        umo = event.unified_msg_origin
        now = time.time()
        st = self._state.get(umo)
        if st and st["text"] == text and now - st["ts"] <= float(cfg["window"]):
            st["count"] += 1
            st["senders"].add(sender)
        else:
            # 同一句话但间隔超窗口：这不是 bug 就是真的聊别的去了，
            # 记一行日志，下次再有人问「怎么没复读」直接能对上
            if st and st["text"] == text:
                logger.info(
                    f"[repeat] chain broken: gap {now - st['ts']:.0f}s > "
                    f"{cfg['window']}s, count was {st['count']}"
                )
            st = {"text": text, "count": 1, "senders": {sender}, "ts": now}
        st["ts"] = now
        self._state[umo] = st

        if st["count"] < int(cfg["threshold"]):
            # 只差一条时留个念想，方便判断是没触发还是没攒够
            if st["count"] > 1:
                logger.info(f"[repeat] {st['count']}/{cfg['threshold']} {text[:16]}")
            return
        if len(st["senders"]) < int(cfg["min_senders"]):
            logger.info(
                f"[repeat] {st['count']}x from {len(st['senders'])} sender(s), "
                f"need {cfg['min_senders']} — 一个人刷屏不算复读"
            )
            return

        last = self._echoed.get(umo)
        if last and last[0] == text and now - last[1] < float(cfg["cooldown"]):
            return

        # 先落状态再 await：两个事件挤在一起时，也只有第一个能走到发送
        st["count"] = 0
        st["senders"] = set()
        self._echoed[umo] = (text, now)

        await event.send(event.plain_result(text))
        event.stop_event()
        logger.info(f"[repeat] echo in {group_id or umo}: {text[:24]}")
