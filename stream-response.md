Streaming responses
By default, the model returns a response only after the entire generation process is complete.

For more fluid interactions, use streaming to receive GenerateContentResponse instances incrementally as they're generated.

```Python
from google import genai
from google.genai import types

client = genai.Client()

prompt = """
Alice, Bob, and Carol each live in a different house on the same street: red, green, and blue.
The person who lives in the red house owns a cat.
Bob does not live in the green house.
Carol owns a dog.
The green house is to the left of the red house.
Alice does not own a cat.
Who lives in each house, and what pet do they own?
"""

thoughts, answer = [], []

stream = client.models.generate_content_stream(
    model="gemini-2.5-pro",
    contents=prompt,
    config=types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(
            include_thoughts=True,
            # thinking_budget=-1,   # dynamic
            # thinking_budget=0,    # disable (if model supports)
            # thinking_budget=1024, # explicit
        )
    ),
)

print("Streaming...\n")
got_thoughts = False
got_answer = False

for chunk in stream:
    for part in chunk.candidates[0].content.parts:
        if not part.text:
            continue
        if getattr(part, "thought", False):
            if not got_thoughts:
                print("Thoughts summary:")
                got_thoughts = True
            print(part.text, end="", flush=True)
            thoughts.append(part.text)
        else:
            if not got_answer:
                print("\n\nAnswer:")
                got_answer = True
            print(part.text, end="", flush=True)
            answer.append(part.text)

print("\n\n---\nFinal thoughts summary:\n", "".join(thoughts))
print("\nFinal answer:\n", "".join(answer))

```

Short answer: **it depends on the model.**

* **2.5 Pro** — **Yes.** Thinking is on by default (dynamic) and **can’t be disabled**.
* **2.5 Flash / Flash Preview** — **Yes by default** (dynamic), but you **can disable** it with `thinkingBudget: 0`.
* **2.5 Flash-Lite / Flash-Lite Preview** — **No by default.** It doesn’t think unless you set a budget (e.g., `thinkingBudget: 1024` or `-1` for dynamic).
* **Robotics-ER 1.5 Preview** — **Yes by default** (dynamic); can disable with `0`.
* **2.5 Flash Live Native Audio (09-2025)** — **Yes by default** (dynamic); can disable with `0`.

Tip: regardless of whether thinking is on, you’ll **only see thought summaries** if you set `includeThoughts: true`.
