# AnyJSON

让模型输出强约束 JSON：
- 按 schema 校验字段与类型
- 不符合时自动重试（默认 3 次）
- 超过重试次数仍失败则抛错

## 使用（uv）

```bash
uv sync
```

```python
from openai import OpenAI
from anyjson import AnyJSON

client = OpenAI()  # 自动读取 OPENAI_API_KEY
generator = AnyJSON(client, repeat=3)  # repeat 可选，默认 3

result = generator.gen(
    "把西红柿炒蛋任务分解最后一个任务是int1",
    {"step1": str, "step2": str, "step3": int},
)
print(result)
```

## 行为

- 返回值：`dict`
- 必须和 schema 键完全一致（不允许缺失或多余）
- 类型严格校验（例如 `int` 不接受 `bool`）
- 所有尝试失败后抛出 `AnyJSONGenerationError`
