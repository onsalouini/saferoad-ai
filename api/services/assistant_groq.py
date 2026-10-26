# api/services/assistant_groq.py
"""
Fournisseur Groq pour le copilote (gratuit avec limites, modèles open source).
API compatible OpenAI (chat/completions) appelée en streaming SSE avec httpx ; mêmes outils
et mêmes événements NDJSON que le fournisseur Claude (voir services/assistant.py).
"""
from __future__ import annotations

import json
import os
from typing import AsyncIterator, Callable

import httpx

URL = os.getenv("GROQ_URL", "https://api.groq.com/openai/v1/chat/completions")
MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")


def available() -> bool:
    return bool(os.getenv("GROQ_API_KEY"))


def _tools_schema(tools) -> list[dict]:
    return [{"type": "function", "function": {"name": t.name, "description": t.description,
                                              "parameters": t.input_schema}} for t in tools]


async def stream(system: str, messages: list[dict], tools, labels: dict[str, str], max_turns: int,
                 event: Callable[..., str], pending_events: list[dict]) -> AsyncIterator[tuple[str, dict | None]]:
    """
    Produit des couples (ligne NDJSON à transmettre, consommation du tour ou None).
    Les outils sont exécutés entre deux tours ; les événements qu'ils produisent (ex. « trip »)
    sont ajoutés à `pending_events` et transmis par l'appelant.
    """
    history = [{"role": "system", "content": system}] + messages
    headers = {"Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}"}
    by_name = {t.name: t for t in tools}
    async with httpx.AsyncClient(timeout=httpx.Timeout(90, connect=10), headers=headers) as client:
        for _ in range(max_turns):
            payload = {"model": MODEL, "messages": history, "stream": True, "temperature": 0.3,
                       "max_completion_tokens": 4096}
            if tools:
                payload.update(tools=_tools_schema(tools), tool_choice="auto")
            text, calls, usage, finish = "", {}, None, "stop"
            async with client.stream("POST", URL, json=payload) as r:
                if r.status_code >= 400:
                    body = (await r.aread()).decode(errors="replace")
                    raise httpx.HTTPStatusError(f"Groq {r.status_code}: {body[:300]}", request=r.request, response=r)
                async for line in r.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:].strip()
                    if data == "[DONE]":
                        break
                    chunk = json.loads(data)
                    usage = (chunk.get("x_groq") or {}).get("usage") or chunk.get("usage") or usage
                    for choice in chunk.get("choices", []):
                        delta = choice.get("delta") or {}
                        if delta.get("content"):
                            text += delta["content"]
                            yield event("text", text=delta["content"]), None
                        for tc in delta.get("tool_calls") or []:
                            slot = calls.setdefault(tc.get("index", 0), {"id": "", "name": "", "arguments": ""})
                            slot["id"] = tc.get("id") or slot["id"]
                            fn = tc.get("function") or {}
                            slot["name"] += fn.get("name") or ""
                            slot["arguments"] += fn.get("arguments") or ""
                        finish = choice.get("finish_reason") or finish
            yield "", usage
            if finish == "length":
                yield event("text", text="\n\n(Réponse tronquée.)"), None
                return
            if not calls:
                return

            ordered = [calls[i] for i in sorted(calls)]
            history.append({"role": "assistant", "content": text or None, "tool_calls": [
                {"id": c["id"], "type": "function", "function": {"name": c["name"], "arguments": c["arguments"] or "{}"}}
                for c in ordered]})
            for c in ordered:
                yield event("tool", name=c["name"], label=labels.get(c["name"], c["name"])), None
                tool = by_name.get(c["name"])
                try:
                    args = json.loads(c["arguments"] or "{}")
                    result = await tool.call(args) if tool else json.dumps({"erreur": "outil inconnu"})
                except (json.JSONDecodeError, TypeError, ValueError) as e:
                    result = json.dumps({"erreur": f"arguments invalides : {e}"}, ensure_ascii=False)
                while pending_events:
                    e = pending_events.pop(0)
                    yield event(e.pop("type"), **e), None
                history.append({"role": "tool", "tool_call_id": c["id"], "content": str(result)})
        yield event("text", text="\n\n(Trop d'étapes : reformulez votre question.)"), None
