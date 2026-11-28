# astrbot-plugin-repeat

群聊复读机：**同一句话连刷三条以上，跟着复读一次**。
适用于 [AstrBot](https://github.com/AstrBotDevs/AstrBot) 4.28+。

## 它做什么
群里出现连续的相同纯文本消息时，满足条件就跟着复读一句，如：

```
A: 哈哈哈哈
B: 哈哈哈哈
C: 哈哈哈哈
阿灰: 哈哈哈哈      ← 只这一条，不会再多说别的
```

## 安装

```bash
cd AstrBot/data/plugins
git clone https://github.com/zincvolt/astrbot-plugin-repeat.git astrbot_plugin_repeat
```

重启 AstrBot（不用重启 QQ）。插件用 `plugin_set: ["*"]` 的默认配置会自动启用。


## 配置

插件目录下的 `repeat.json`，改完保存即生效 ：

```json
{
  "enabled": true,
  "threshold": 3,
  "window": 240,
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
| `window` | 两条之间最多隔多久仍算「连续」（秒） | `240` |
| `cooldown` | 同一段文本两次复读的最小间隔（秒） | `300` |
| `min_senders` | 至少几个不同的人参与 | `2` |
| `max_len` | 超过这个长度的消息不参与（字符） | `60` |
| `disabled_groups` | 不生效的群号列表，如 `["123456"]` | `[]` |
