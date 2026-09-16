"""离线单元测试：不依赖真实 AstrBot 运行环境，用假 event 验证清洗逻辑。

在插件目录内直接运行：
    python test_offline.py

需要能 import 到 astrbot 的消息组件（Plain/Image），例如在 AstrBot
容器内执行，或本机装有 astrbot 包。
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from astrbot.api.message_components import Image, Plain

import main as m


class FakeResult:
    def __init__(self, chain):
        self.chain = chain


class FakeEvent:
    def __init__(self, chain):
        self._r = FakeResult(chain)

    def get_result(self):
        return self._r


def make_inst(cfg=None):
    inst = m.BlockToolCallPlaceholder.__new__(m.BlockToolCallPlaceholder)
    inst.config = cfg or {}
    inst._compile_rules()
    return inst


async def run():
    # 用默认规则（无配置）构造，等价于 WebUI 未改动时的行为
    inst = make_inst()
    h = m.BlockToolCallPlaceholder.strip_toolcall_placeholder

    # 1. 纯占位 -> 清空
    ev = FakeEvent([Plain(text="Model generated function call(s).")])
    await h(inst, ev)
    assert ev.get_result().chain == [], "case1 fail"

    # 2. finishReason 调试转储 -> 清空
    ev = FakeEvent(
        [Plain(text="finishReason: STOP\nfinishMessage: Model generated function call(s).")]
    )
    await h(inst, ev)
    assert ev.get_result().chain == [], "case2 fail"

    # 3. 正常文本 -> 不动
    ev = FakeEvent([Plain(text="回主人，这是正常回复")])
    await h(inst, ev)
    out = ev.get_result().chain
    assert len(out) == 1 and out[0].text == "回主人，这是正常回复", "case3 fail"

    # 4. 垃圾行混在正常文本中 -> 只留正常行
    ev = FakeEvent(
        [
            Plain(
                text="回主人，看这个：\nfinishReason: STOP\nfinishMessage: Model generated function call(s).\n以上是调试信息"
            )
        ]
    )
    await h(inst, ev)
    out = ev.get_result().chain
    assert len(out) == 1 and out[0].text == "回主人，看这个：\n以上是调试信息", (
        f"case4 fail: {out[0].text!r}"
    )

    # 5. 占位+图片 -> 只剩图片
    ev = FakeEvent([Plain(text="Model generated function call(s)."), Image(file="x")])
    await h(inst, ev)
    out = ev.get_result().chain
    assert len(out) == 1 and isinstance(out[0], Image), "case5 fail"

    # 6. 带空白占位 -> 清空
    ev = FakeEvent([Plain(text="  Model generated function call(s).  ")])
    await h(inst, ev)
    assert ev.get_result().chain == [], "case6 fail"

    # 7. 空结果 -> 不炸
    ev = FakeEvent([])
    await h(inst, ev)
    assert ev.get_result().chain == [], "case7 fail"

    # 8. 自定义规则（替换默认规则）
    inst8 = make_inst({"拦截规则": ["^广告：.*$"]})
    ev = FakeEvent([Plain(text="正常内容\n广告：点此购买")])
    await h(inst8, ev)
    out = ev.get_result().chain
    assert len(out) == 1 and out[0].text == "正常内容", f"case8 fail: {out}"
    # 自定义后默认规则不应再拦截
    ev = FakeEvent([Plain(text="Model generated function call(s).")])
    await h(inst8, ev)
    assert len(ev.get_result().chain) == 1, "case8b fail: custom rules must replace defaults"

    # 9. 行内包含匹配模式：垃圾内容夹在句中 -> 整行剔除
    inst9 = make_inst({"拦截规则": ["内部渠道号\\d+"], "行内包含匹配": True})
    ev = FakeEvent([Plain(text="这句话里夹了内部渠道号9527要删掉")])
    await h(inst9, ev)
    assert ev.get_result().chain == [], "case9 fail"
    # 整行匹配模式下同样的内容不动
    inst9b = make_inst({"拦截规则": ["内部渠道号\\d+"]})
    ev = FakeEvent([Plain(text="这句话里夹了内部渠道号9527要删掉")])
    await h(inst9b, ev)
    assert len(ev.get_result().chain) == 1, "case9b fail: whole-line mode must keep the line"

    # 10. 替代文本：整条被清空时以替代文本发送
    inst10 = make_inst({"替代文本": "（回复被过滤）"})
    ev = FakeEvent([Plain(text="Model generated function call(s).")])
    await h(inst10, ev)
    out = ev.get_result().chain
    assert len(out) == 1 and out[0].text == "（回复被过滤）", f"case10 fail: {out}"

    # 11. 无效正则：跳过并继续工作，正常规则仍生效
    inst11 = make_inst({"拦截规则": ["(", "finishReason\\s*:.*"]})
    assert len(inst11._rules) == 1, "case11 fail: invalid regex should be skipped"
    ev = FakeEvent([Plain(text="finishReason: STOP")])
    await h(inst11, ev)
    assert ev.get_result().chain == [], "case11b fail"

    print("ALL TESTS PASSED")


asyncio.run(run())
