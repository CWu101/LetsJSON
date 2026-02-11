# LetsJSON

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
from letsjson import LetsJSON

client = OpenAI(
    api_key = "your_api_key",
    base_url = "your_base_url",
) 
generator = LetsJSON(
    client=client,
    model="your_model",  # 必填
    repeat=3,              # 可选，默认 3
)

schema = {
    "title": str,
    "steps": [{"name": str, "minutes": int}],
}

result = generator.gen("给我一个 30 分钟早餐计划", schema)
print(result)

```

## API

- `LetsJSON(client, model, repeat=3)`
- `gen(prompt: str, schema: dict[str, Any]) -> dict[str, Any]`
- `schema` 顶层必须是 `dict`

## Schema 支持

- 对象：`{"name": str, "age": int}`
- 列表：`{"items": [str]}`（列表 schema 必须且只能有 1 个元素类型）
- 嵌套：`{"user": {"name": str}, "tags": [str]}`
- 类型严格校验：
  - `int` 不接受 `bool`
  - `float` 接受 `int` 和 `float`（不接受 `bool`）

## 行为

- 返回值始终是 `dict`
- 对象键必须和 schema 完全一致（不允许缺失或多余）
- 每次失败后会把上次错误拼到下一次提示词里继续重试
- 重试耗尽后抛出 `LetsJSONGenerationError`

## OpenAI 客户端兼容性

- 优先调用 `client.chat.completions.create(...)`
- 失败时回退到 `client.responses.create(...)`
- 两者都不可用或都失败时抛出 `LetsJSONGenerationError`

## 输出解析容错

- 优先直接 `json.loads(...)`
- 若模型返回了额外文本/Markdown，会尝试提取 JSON 代码块或首个完整 JSON 片段再解析
- 无法解析合法 JSON 时抛出 `LetsJSONValidationError`
