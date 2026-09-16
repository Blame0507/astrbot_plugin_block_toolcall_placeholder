"""屏蔽中转网关在工具调用时注入的占位/调试文本。

部分 one-api/new-api 类网关在模型返回 tool_calls 时，会在 assistant content 里
塞入 "Model generated function call(s)." 占位字符串，或输出
"finishReason: STOP / finishMessage: ..." 这样的调试转储。
AstrBot 会把这些 content 当作普通回复发到群里，造成刷屏/信息泄露。
本插件在消息装饰阶段按行剔除这类垃圾文本（混在正常文本里也能剥掉）。
"""

import re

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import Plain
from astrbot.api.star import Context, Star, register

# 匹配整行网关垃圾文本：
#   Model generated function call(s).
#   finishReason: STOP
#   finishMessage: Model generated function call(s).
_JUNK_LINE_RE = re.compile(
    r"^\s*(?:Model generated function call.*|finishReason\s*:.*|finishMessage\s*:.*)$"
)


@register(
    "block_toolcall_placeholder",
    "kimi",
    "屏蔽中转网关在工具调用时注入的占位文本",
    "1.1.0",
)
class BlockToolCallPlaceholder(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    @staticmethod
    def _clean_text(text: str):
        """剔除垃圾行。返回 None 表示无垃圾行；否则返回清洗后文本（可为空串）。"""
        lines = text.splitlines()
        kept = [ln for ln in lines if not _JUNK_LINE_RE.match(ln)]
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
            result.chain[:] = new_chain
            logger.info(
                f"[block_toolcall_placeholder] 已拦截网关占位/调试文本"
                f"（移除 {removed} 个组件，清洗 {cleaned_n} 段文本）"
            )
