# astrbot-plugin-repeat

群聊复读机：**同一句话连刷三条以上，跟着复读一次**。带冷却和去重，不会复读个没完。

适用于 [AstrBot](https://github.com/AstrBotDevs/AstrBot) 4.28+。

## 它做什么

群里出现连续的相同纯文本消息时，满足条件就跟着复读一句（原文，不加表情、不加话）：

```
A: 哈哈哈哈
B: 哈哈哈哈
C: 哈哈哈哈
阿灰: 哈哈哈哈      ← 只这一条，不会再多说别的
```

## 它不做什么

- **不会重复复读**：复读完立刻清零，同一段文本默认 300 秒内不再复读
- **不会把人刷屏当复读素材**：至少要 2 个不同的人发（`min_senders`）
- **不复读指令**：`/` `／` 开头的直接跳过，不跟别的插件抢
- **不复读非纯文本**：图片、语音、引用回复、@ 一律不参与，避免复读出 `[图片]`
- **不复读内部标记**：带 `&&` / `$$` 的消息（表情、情绪标记）直接跳过
- **不会复读之后又被模型接一句**：复读发出后 `stop_event()`，判官/主动回复不会再补一句

## 安装

```bash
cd AstrBot/data/plugins
git clone https://github.com/zincvolt/astrbot-plugin-repeat.git astrbot_plugin_repeat
```

重启 AstrBot（不用重启 QQ）。插件用 `plugin_set: ["*"]` 的默认配置会自动启用。

无第三方依赖，只用 AstrBot 自带的 API。

## 配置

插件目录下的 `repeat.json`，改完保存即生效（按 mtime 热读，不用重启）：

```json
{
  "enabled": true,
  "threshold": 3,
  "window": 120,
  "cooldown": 300,
  "min_senders": 2,
  "max_len": 60,
  "disabled_groups": []
}
```

| 字段 | 含义 | 默认 |
|---|---|---|
| `enabled` | 总开关 | `true` |
| `threshold` | 连续几条相同才复读 | `3` |
| `window` | 两条之间最多隔多久仍算「连续」（秒） | `120` |
| `cooldown` | 同一段文本两次复读的最小间隔（秒） | `300` |
| `min_senders` | 至少几个不同的人参与 | `2` |
| `max_len` | 超过这个长度的消息不参与（字符） | `60` |
| `disabled_groups` | 不生效的群号列表，如 `["123456"]` | `[]` |

## 实现要点

- 状态只在内存里（`umo -> {text, count, senders, ts}`），重启清零，不写文件
- handler 注册在 `priority=maxsize - 1`，早于 AstrBot 内置的群聊上下文 / 主动回复
  （`maxsize-1`、`maxsize-2`）执行；不命中就立刻返回，不影响正常聊天；
  留出一档给别的命令类插件（如兽聚），避免同一条消息既出卡又被复读
- 计数与清零都在 `await event.send(...)` 之前完成，两个事件抢同一条消息时也只会发一次

## 许可

AGPL-3.0
