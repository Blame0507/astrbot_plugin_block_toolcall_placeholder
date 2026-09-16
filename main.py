"""屏蔽中转网关在工具调用时注入的占位/调试文本。

部分 one-api/new-api 类网关在模型返回 tool_calls 时，会在 assistant content 里
塞入 "Model generated function call(s)." 占位字符串，或输出
"finishReason: STOP / finishMessage: ..." 这样的调试转储。
AstrBot 会把这些 content 当作普通回复发到群里，造成刷屏/信息泄露。
本插件在消息装饰阶段按行剔除这类垃圾文本（混在正常文本里也能剥掉）。

拦截规则可在 AstrBot WebUI 的插件配置面板中自定义（正则表达式列表）。
"""

import re

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import Plain
from astrbot.api.star import Context, Star, register

# 默认规则：已知网关垃圾行。用户清空配置面板的规则列表时退回此组。
DEFAULT_RULES = [
    "Model generated function call.*",
    r"finishReason\s*:.*",
    r"finishMessage\s*:.*",
]


@register(
    "block_toolcall_placeholder",
    "kimi",
    "屏蔽中转网关在工具调用时注入的占位文本（支持自定义规则）",
    "1.2.0",
)
class BlockToolCallPlaceholder(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self._compile_rules()

    def _compile_rules(self) -> None:
        """读取 WebUI 配置并编译拦截规则；无效正则告警并跳过。"""
        self._rules = []
        for raw in self.config.get("拦截规则") or DEFAULT_RULES:
            try:
                self._rules.append(re.compile(raw))
            except re.error as e:
                logger.warning(
                    f"[block_toolcall_placeholder] 无效正则已跳过：{raw!r}（{e}）"
                )
        self._substring = bool(self.config.get("行内包含匹配", False))
        self._fallback = (self.config.get("替代文本") or "").strip()

    def _is_junk_line(self, line: str) -> bool:
        for rule in self._rules:
            if self._substring:
                if rule.search(line):
                    return True
            elif rule.fullmatch(line.strip()):
                return True
        return False

    def _clean_text(self, text: str):
        """剔除垃圾行。返回 None 表示无垃圾行；否则返回清洗后文本（可为空串）。"""
        lines = text.splitlines()
        kept = [ln for ln in lines if not self._is_junk_line(ln)]
        if len(kept) == len(lines):
            return None
        return "\n".join(kept).strip()

    @filter.on_decorating_result()
    async def strip_toolcall_placeholder(self, event: AstrMessageEvent):
        result = event.get_result()
        if result is None or not result.chain:
            return
        new_chain = []
        removed = 0
        cleaned_n = 0
        for comp in result.chain:
            if isinstance(comp, Plain):
                cleaned = self._clean_text(comp.text)
                if cleaned is not None:
                    if cleaned:
                        new_chain.append(Plain(text=cleaned))
                        cleaned_n += 1
                    else:
                        removed += 1
                    continue
            new_chain.append(comp)
        if removed or cleaned_n:
            if not new_chain and self._fallback:
                new_chain.append(Plain(text=self._fallback))
            result.chain[:] = new_chain
            logger.info(
                f"[block_toolcall_placeholder] 已拦截网关占位/调试文本"
                f"（移除 {removed} 个组件，清洗 {cleaned_n} 段文本）"
            )
