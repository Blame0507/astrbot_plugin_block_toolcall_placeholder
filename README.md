# astrbot_plugin_block_toolcall_placeholder

屏蔽 one-api / new-api 类中转网关在模型返回 tool_calls 时注入的占位/调试文本。

## 背景

部分 one-api / new-api 类 LLM 中转网关有一个恶习：当模型返回 `tool_calls` 时，网关会往 assistant content 里塞入垃圾文本，AstrBot 会把它当作普通回复原样发到群里，造成刷屏甚至信息泄露。已见到的形态：

1. 整段占位字符串：

   ```
   Model generated function call(s).
   ```

2. 调试转储：

   ```
   finishReason: STOP
   finishMessage: Model generated function call(s).
   ```

## 实现方式

插件挂载 AstrBot 的 `on_decorating_result` 钩子，在消息发出前**按行**剔除匹配以下正则的行（整段删光则整条消息不发；垃圾行混在正常文本里则只删垃圾行，正常内容保留）：

```python
_JUNK_LINE_RE = re.compile(
    r"^\s*(?:Model generated function call.*|finishReason\s*:.*|finishMessage\s*:.*)$"
)
```

不修改 AstrBot 核心代码，纯插件实现，卸载即恢复原状。

## 安装

### 方式一：WebUI 插件市场 / 从 URL 安装

在 AstrBot WebUI → 插件管理 → 从仓库安装，填入本仓库地址。

### 方式二：手动安装

```bash
cd AstrBot/data/plugins
git clone https://github.com/Blame0507/astrbot_plugin_block_toolcall_placeholder.git
```

然后重启 AstrBot（`docker restart astrbot` 或重启进程）即可，加载日志中应出现 `block_toolcall_placeholder`。

## 配置（WebUI 可视化面板）

在 AstrBot WebUI → 插件管理 → 本插件 → 配置，无需改代码：

| 配置项 | 类型 | 默认 | 说明 |
|---|---|---|---|
| 拦截规则 | 正则列表 | 预置三条已知网关垃圾行规则 | 每条为一个 Python 正则表达式；某行（忽略首尾空白）完全命中任一规则即整行剔除 |
| 行内包含匹配 | 开关 | 关 | 默认整行匹配（更安全）。开启后行内任意位置命中即整行剔除，更激进，可能误伤正常回复 |
| 替代文本 | 文本 | 空 | 整条消息被过滤干净时：留空则不发送任何内容；填写则以该文本替代发送 |

无效正则会被自动跳过并在日志中提示，不会导致插件崩溃。配置保存后即按新规则拦截。

默认预置规则（可删改）：

```text
Model generated function call.*
finishReason\s*:.*
finishMessage\s*:.*
```

## 文件说明

| 文件 | 说明 |
|---|---|
| `main.py` | 插件本体（钩子 + 清洗逻辑） |
| `metadata.yaml` | AstrBot 插件元数据 |
| `test_offline.py` | 离线单元测试（7 组用例，用假 event 验证） |


## License

[MIT](./LICENSE)
