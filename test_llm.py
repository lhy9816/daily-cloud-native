import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from openai import OpenAI
from pathlib import Path

client = OpenAI(
    api_key="sk-QmhH5llW5ThJW5tK3WPj3RbVakCvxQWolXiswzAJGrNmU1KP",
    base_url="https://aiproxy.xin/cosphere/v1",
)
prompt = Path("prompts/github_prompt.md").read_text(encoding="utf-8")
user_msg = "title: lmdeploy\nlink: https://github.com/InternLM/lmdeploy\ncontent: LMDeploy is a toolkit for compressing and deploying large language models.\nstars: 12000"

r = client.chat.completions.create(
    model="glm-4.5-air",
    messages=[{"role": "system", "content": prompt}, {"role": "user", "content": user_msg}],
    max_tokens=2000,
    temperature=0.3,
)
ct = r.choices[0].message.content or ""
print("len:", len(ct))
print("finish:", r.choices[0].finish_reason)
print("---")
print(ct[:500])
