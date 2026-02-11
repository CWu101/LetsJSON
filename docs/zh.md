# LetsJSON
让 LLM 按你定义的格式生成 JSON。

让模型输出强约束 JSON：
- 按 schema 校验字段与类型
- 不符合时自动重试（默认 3 次）
- 超过重试次数仍失败则抛错或返回空值

## 安装

```bash
uv add letsjson
```

或者：

```bash
pip install letsjson
```

## 使用

```python
from openai import OpenAI
from letsjson import LetsJSON

client = OpenAI(
    api_key="你的 API key",
    base_url="你的 API base URL",
)
generator = LetsJSON(client, model="你的 model name")  # repeat 可选，默认 3

schema = {
    "title": str,
    "steps": [{"time": str, "location": str, "detail": str}],
}
result = generator.gen("给我一个2天1夜的上海旅游计划", schema)
print(result)
```

## Schema 支持

- 对象：`{"name": str, "age": int}`
- 列表：`{"items": [str]}`（列表 schema 必须且只能有 1 个元素类型）
- 嵌套：`{"user": {"name": str}, "tags": [str]}`
- 类型严格校验：
  - `int` 不接受 `bool`
  - `float` 接受 `int` 和 `float`（不接受 `bool`）
