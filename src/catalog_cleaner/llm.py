"""One function to call an LLM: Claude if ANTHROPIC_API_KEY is set, otherwise local Ollama."""

import os


def generate(system: str, user: str, max_tokens: int = 1024) -> str:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _anthropic(system, user, max_tokens)
    return _ollama(system, user, max_tokens)


def _anthropic(system: str, user: str, max_tokens: int) -> str:
    import anthropic

    msg = anthropic.Anthropic(timeout=60, max_retries=1).messages.create(
        model=os.environ.get("CATALOG_MODEL", "claude-sonnet-5-5"),
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in msg.content if b.type == "text")


def _ollama(system: str, user: str, max_tokens: int) -> str:
    import httpx

    url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    model = os.environ.get("CATALOG_OLLAMA_MODEL", "qwen2.5-coder:7b")
    try:
        r = httpx.post(
            f"{url}/api/chat",
            json={
                "model": model,
                "stream": False,
                "options": {"num_predict": max_tokens, "temperature": 0.1},
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            },
            timeout=300,
        )
        r.raise_for_status()
    except httpx.HTTPError as e:
        raise RuntimeError(
            f"Ollama call failed ({e}). Run `ollama serve` and `ollama pull {model}`, "
            "or set ANTHROPIC_API_KEY to use Claude."
        ) from e
    return r.json()["message"]["content"]


def chat(system: str, messages: list, tools: list, max_tokens: int = 1024) -> list[dict]:
    """One tool-using turn with Claude. Returns the reply as plain dicts (text and tool_use blocks)."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("The review agent needs ANTHROPIC_API_KEY (tool use is not supported with the local model).")
    import anthropic

    msg = anthropic.Anthropic(timeout=60, max_retries=1).messages.create(
        model=os.environ.get("CATALOG_MODEL", "claude-sonnet-5-5"),
        max_tokens=max_tokens, system=system, messages=messages, tools=tools,
    )
    return [{"type": "text", "text": b.text} if b.type == "text"
            else {"type": "tool_use", "id": b.id, "name": b.name, "input": b.input}
            for b in msg.content if b.type in ("text", "tool_use")]
