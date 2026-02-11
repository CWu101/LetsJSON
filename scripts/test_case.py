from __future__ import annotations

import os

from letsjson import LetsJSON
from openai import OpenAI

OPENAI_API_KEY= "sk-3olqTkTnAfYt88jm88hkxcFFrQx2cvIZONlPQXjL8Sj5fDau"
OPENAI_BASE_URL= "https://api.moonshot.cn/v1"
OPENAI_MODEL= "kimi-latest"

def main() -> None:
    client = OpenAI(
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL,
    )
    generator = LetsJSON(client, model = OPENAI_MODEL, repeat=3)
    result = generator.gen(
        "把西红柿炒蛋拆成3步，最后一步的序号用整数。",
        {"step1": str, "step2": str, "step3": int},
    )
    print(result)


if __name__ == "__main__":
    main()
