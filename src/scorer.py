import json

import anthropic
from openai import OpenAI

SCORE_SYSTEM = """You score how good a lead a Reddit post is for a product. \
Score 0-100: 0 means completely irrelevant, 100 means the poster is \
describing exactly the problem the product solves and seems ready to hear \
about a solution. Reply with ONLY a JSON object, no markdown fences, no \
other text: {"score": <integer 0-100>, "reason": "<one sentence>"}"""

DRAFT_SYSTEM = """You write a short, genuinely useful Reddit reply to a post, \
in the voice described, that naturally mentions a product where it's \
actually relevant to what the poster asked. Prioritize being helpful over \
being promotional -- a reply that only sells will get removed by moderators \
and ignored by the poster. Also judge, from the source and the post's \
tone, whether mentioning a product openly would likely read as welcome \
self-promotion versus something better said as a low-key direct message \
instead. Reply with ONLY a JSON object, no markdown fences, no other text: \
{"draft_reply": "<the reply text>", "self_promo_allowed": <true|false>}"""

# Substack items are published articles, not people asking for help, so they
# get a different rubric: "is this a good place for a useful comment?"
SCORE_SYSTEM_ARTICLE = """You judge whether a published newsletter article is a \
good place for a thoughtful comment that could reach the product's likely \
buyers. Score 0-100: 0 means unrelated to the problem the product addresses; \
100 means the article is squarely about that problem, its readers look like \
the target buyers, and there is room to add a useful, non-promotional \
perspective. Reply with ONLY a JSON object, no markdown fences, no other \
text: {"score": <integer 0-100>, "reason": "<one sentence>"}"""

DRAFT_SYSTEM_ARTICLE = """You write a short comment to leave under a newsletter \
article, in the voice described. It must respond to a specific point the \
article makes and add a genuinely useful insight or experience. Mention the \
product only if it truly fits the point being made; otherwise leave it out \
entirely. No generic praise. Also judge whether mentioning the product here \
would read as welcome or as promotional. Reply with ONLY a JSON object, no \
markdown fences, no other text: \
{"draft_reply": "<the comment text>", "self_promo_allowed": <true|false>}"""

CLAUDE_SCORE_MODEL = "claude-haiku-4-5-20251001"
CLAUDE_DRAFT_MODEL = "claude-sonnet-5"
DEEPSEEK_MODEL = "deepseek-chat"


class Scorer:
    """Scores and drafts replies using either Claude or DeepSeek, chosen by
    config.yaml's llm_provider. Same JSON-in, JSON-out contract either way,
    so scan.py and the dashboard don't need to know which one ran."""

    def __init__(self, provider: str, anthropic_api_key: str = "", deepseek_api_key: str = ""):
        self.provider = provider.lower().strip()

        if self.provider == "deepseek":
            if not deepseek_api_key:
                raise RuntimeError(
                    "config.yaml sets llm_provider: deepseek, but DEEPSEEK_API_KEY isn't set."
                )
            self.client = OpenAI(api_key=deepseek_api_key, base_url="https://api.deepseek.com")
        elif self.provider == "claude":
            if not anthropic_api_key:
                raise RuntimeError(
                    "config.yaml sets llm_provider: claude, but ANTHROPIC_API_KEY isn't set."
                )
            self.client = anthropic.Anthropic(api_key=anthropic_api_key)
        else:
            raise RuntimeError(
                f"Unknown llm_provider '{provider}' in config.yaml -- use 'claude' or 'deepseek'."
            )

    def score_post(
        self, product_description: str, post_title: str, post_body: str, source_type: str = "reddit"
    ) -> dict:
        prompt = (
            f"Product:\n{product_description}\n\n"
            f"Reddit post title: {post_title}\n"
            f"Reddit post body: {post_body[:1500]}"
        )
        default = {"score": 0, "reason": "parse failure"}
        system = SCORE_SYSTEM_ARTICLE if source_type == "substack" else SCORE_SYSTEM
        if self.provider == "deepseek":
            return self._call_deepseek(DEEPSEEK_MODEL, system, prompt, 150, default)
        return self._call_claude(CLAUDE_SCORE_MODEL, system, prompt, 150, default)

    def draft_reply(
        self,
        product_description: str,
        brand_voice: str,
        post_title: str,
        post_body: str,
        source_label: str,
        source_type: str = "reddit",
    ) -> dict:
        prompt = (
            f"Product:\n{product_description}\n\n"
            f"Brand voice:\n{brand_voice}\n\n"
            f"Source: {source_label}\n"
            f"Post title: {post_title}\n"
            f"Post body: {post_body[:1500]}"
        )
        default = {"draft_reply": None, "self_promo_allowed": None}
        system = DRAFT_SYSTEM_ARTICLE if source_type == "substack" else DRAFT_SYSTEM
        if self.provider == "deepseek":
            return self._call_deepseek(DEEPSEEK_MODEL, system, prompt, 400, default)
        return self._call_claude(CLAUDE_DRAFT_MODEL, system, prompt, 400, default)

    def _call_claude(self, model: str, system: str, prompt: str, max_tokens: int, default: dict) -> dict:
        msg = self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(block.text for block in msg.content if block.type == "text")
        return self._parse_json(text, default)

    def _call_deepseek(self, model: str, system: str, prompt: str, max_tokens: int, default: dict) -> dict:
        resp = self.client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )
        text = resp.choices[0].message.content or ""
        return self._parse_json(text, default)

    @staticmethod
    def _parse_json(text: str, default: dict) -> dict:
        text = text.strip().strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            print(f"[scorer] could not parse model output: {text[:200]!r}")
            return default
