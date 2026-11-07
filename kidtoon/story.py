"""Episode writing and kid-safety review with Claude."""
from __future__ import annotations

import json
from typing import Literal

import anthropic
from pydantic import BaseModel, ConfigDict

from .art import CAST, CAST_BIO, EMOTIONS, SETTINGS, TIMES, FALLBACK_PROP, sanitize_svg

Speaker = Literal["narrator", "Tumble", "Pippa", "Moss"]
CastName = Literal["Tumble", "Pippa", "Moss"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Line(Strict):
    speaker: Speaker
    text: str
    emotion: Literal["happy", "sad", "surprised", "neutral"]


class Scene(Strict):
    setting: Literal["meadow", "forest", "beach", "garden", "pond", "snowy_hill", "bedroom"]
    time_of_day: Literal["morning", "day", "sunset", "night"]
    characters: list[CastName]
    show_prop: bool
    lines: list[Line]


class Episode(Strict):
    title: str
    description: str
    tags: list[str]
    lesson: str
    prop_name: str
    prop_visual: str
    scenes: list[Scene]


class Review(Strict):
    approved: bool
    issues: list[str]


assert set(SETTINGS) == set(Scene.model_fields["setting"].annotation.__args__)
assert set(TIMES) == set(Scene.model_fields["time_of_day"].annotation.__args__)
assert set(EMOTIONS) == set(Line.model_fields["emotion"].annotation.__args__)

SAFETY_RULES = """\
- Gentle, warm and positive. No violence, scary peril, villains, weapons, injuries, death, bullying that goes unresolved, or frightening imagery.
- No unsafe behaviour a child could copy (no climbing high things, playing with fire, eating unknown plants/berries, swimming alone, talking to strangers, going off alone).
- No brands, real people, existing cartoon characters, products, ads, links, or calls to "subscribe", "comment", or buy anything (YouTube Made-for-Kids rules).
- No requests for personal information. No romance, gross-out humour, rude words or sarcasm.
- Vocabulary simple enough for ages {age}; short sentences; one clear, kind lesson.
- Factual claims (animals, nature, numbers, colours) must be correct."""


def _schema(model: type[BaseModel]) -> dict:
    return {"type": "json_schema", "schema": model.model_json_schema()}


def _call(client: anthropic.Anthropic, model: str, system: str, prompt: str, out: type[BaseModel] | None,
          effort: str = "high", max_tokens: int = 16000):
    output_config: dict = {"effort": effort}
    if out is not None:
        output_config["format"] = _schema(out)
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        output_config=output_config,
        messages=[{"role": "user", "content": prompt}],
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError("Model declined the request")
    if resp.stop_reason == "max_tokens":
        raise RuntimeError("Response was cut off (max_tokens)")
    text = next(b.text for b in resp.content if b.type == "text")
    return out.model_validate_json(text) if out is not None else text


def _validate(ep: Episode, target_minutes: float) -> list[str]:
    problems = []
    if not 4 <= len(ep.scenes) <= 9:
        problems.append(f"need 4-9 scenes, got {len(ep.scenes)}")
    words = sum(len(l.text.split()) for s in ep.scenes for l in s.lines)
    lo, hi = int(target_minutes * 100), int(target_minutes * 170)
    if not lo <= words <= hi:
        problems.append(f"total spoken words should be {lo}-{hi}, got {words}")
    for i, s in enumerate(ep.scenes):
        if not 1 <= len(s.characters) <= 3 or len(set(s.characters)) != len(s.characters):
            problems.append(f"scene {i+1}: 1-3 distinct characters required")
        for l in s.lines:
            if l.speaker != "narrator" and l.speaker not in s.characters:
                problems.append(f"scene {i+1}: {l.speaker} speaks but is not in the scene")
            if len(l.text) > 220:
                problems.append(f"scene {i+1}: a line is too long (max 220 chars)")
    if len(ep.title) > 90:
        problems.append("title longer than 90 characters")
    return problems


def write_episode(cfg: dict, history: list[dict], log=print) -> tuple[Episode, str]:
    client = anthropic.Anthropic()
    model = cfg["model"]
    age = cfg["audience_age"]
    recent = "\n".join(f"- {h['title']} (lesson: {h['lesson']})" for h in history[-40:]) or "- (none yet)"
    cast = "\n".join(f"- {n}: {b}" for n, b in CAST_BIO.items())
    rules = SAFETY_RULES.format(age=age)

    system = f"""You are the head writer of "{cfg['channel_name']}", an original animated YouTube show for children aged {age}.
Recurring cast (the only characters who can appear or speak, plus a narrator):
{cast}

Every episode is a short, cosy, self-contained story with a beginning, a small gentle problem, and a happy resolution
that shows one kind, practical lesson (sharing, patience, trying again, counting, colours, seasons, feelings, helping, etc.).
Each episode features one special object (the "prop") that matters to the story.

Hard rules:
{rules}

Writing style: the narrator sets each scene in one or two sentences; characters then talk in short, lively lines.
Use gentle repetition, a little rhyme or counting where it fits, and end with the narrator restating the lesson warmly
and saying goodbye until next time (do not ask viewers to subscribe or comment)."""

    prompt = f"""Write a brand new episode about {cfg['target_minutes']} minutes long when read aloud
(about {int(cfg['target_minutes'] * 135)} spoken words in total), in 5-7 scenes.

Recent episodes - do NOT repeat their plot, prop or lesson:
{recent}

Field guidance:
- title: catchy, under 70 characters, no emoji-only titles, no clickbait.
- description: 2-4 friendly sentences for parents describing the story and the lesson.
- tags: 8-12 short search tags.
- prop_visual: a concrete visual description of the prop (shape, colours, face or no face) so an illustrator can draw it.
- scenes[].characters: who is on screen (1-3); anyone who speaks in the scene must be listed.
- scenes[].show_prop: true when the prop is visible in that scene.
- lines[].emotion: the speaker's facial expression for that line."""

    feedback = ""
    for attempt in range(1, 4):
        log(f"  writing episode (attempt {attempt})")
        ep = _call(client, model, system, prompt + feedback, Episode)
        problems = _validate(ep, cfg["target_minutes"])
        if not problems:
            review = review_episode(client, model, ep, rules, age)
            if review.approved:
                break
            problems = review.issues
            log(f"  safety review rejected: {problems}")
        else:
            log(f"  validation problems: {problems}")
        feedback = ("\n\nYour previous draft was rejected. Write a NEW draft that fixes these problems:\n- "
                    + "\n- ".join(problems))
    else:
        raise RuntimeError(f"Could not produce an approved episode: {problems}")

    log(f"  approved: {ep.title!r}")
    prop_svg = draw_prop(client, model, ep, log)
    return ep, prop_svg


def review_episode(client, model: str, ep: Episode, rules: str, age: str) -> Review:
    system = (f"You are a strict children's-media standards reviewer for a YouTube channel for ages {age}. "
              "Approve only scripts that fully meet every rule. Be concrete about any issue you find.")
    prompt = (f"Rules:\n{rules}\n\nScript (JSON):\n{ep.model_dump_json(indent=1)}\n\n"
              "Review title, description, tags and every line. Set approved=false if anything breaks a rule; "
              "list each issue as an actionable fix. If approved, issues must be empty.")
    return _call(client, model, system, prompt, Review, effort="high", max_tokens=4000)


def draw_prop(client, model: str, ep: Episode, log=print) -> str:
    system = ("You are an illustrator for a flat, rounded, colourful preschool cartoon. "
              "You draw using plain SVG only.")
    prompt = f"""Draw "{ep.prop_name}": {ep.prop_visual}

Requirements:
- Output ONLY the SVG markup, starting with <svg and ending with </svg>.
- viewBox="0 0 300 300", transparent background, the object centred and filling most of the box.
- Use only basic shapes and paths (rect, circle, ellipse, path, polygon, line, g, linearGradient/radialGradient in defs).
- Thick rounded outlines in a darker shade, bright friendly colours, no text, no <image>, no <style>, no <use>, no links."""
    for attempt in range(2):
        try:
            raw = _call(client, model, system, prompt, None, effort="medium", max_tokens=12000)
            svg = sanitize_svg(raw)
            if svg:
                return svg
            log("  prop SVG failed sanitising, retrying")
        except Exception as e:  # noqa: BLE001
            log(f"  prop drawing failed: {e}")
    log("  using fallback prop")
    return FALLBACK_PROP


def demo_episode() -> tuple[Episode, str]:
    """A built-in episode for testing the render pipeline without an API key."""
    data = {
        "title": "Tumble and the Lost Red Kite",
        "description": "Tumble's red kite floats away on a windy day! With help from Pippa and Moss, he learns that asking friends for help makes big problems feel small.",
        "tags": ["kids cartoon", "story for kids", "friendship", "asking for help", "preschool"],
        "lesson": "When something feels too big, it's okay to ask your friends for help.",
        "prop_name": "red kite",
        "prop_visual": "a diamond-shaped red kite with a yellow cross and a wiggly tail of blue bows",
        "scenes": [
            {"setting": "meadow", "time_of_day": "morning", "characters": ["Tumble"], "show_prop": True, "lines": [
                {"speaker": "narrator", "text": "One breezy morning in Maple Meadow, Tumble the bear cub had a brand new kite.", "emotion": "happy"},
                {"speaker": "Tumble", "text": "Look at my red kite! Up, up, up it goes!", "emotion": "happy"},
                {"speaker": "narrator", "text": "But then, whoosh! A big gust of wind tugged the string right out of his paws.", "emotion": "surprised"},
                {"speaker": "Tumble", "text": "Oh no! Come back, kite!", "emotion": "surprised"}]},
            {"setting": "forest", "time_of_day": "day", "characters": ["Tumble", "Pippa"], "show_prop": False, "lines": [
                {"speaker": "Pippa", "text": "Tumble, why do you look so sad?", "emotion": "neutral"},
                {"speaker": "Tumble", "text": "My kite flew away. I tried to find it all by myself, but I can't.", "emotion": "sad"},
                {"speaker": "Pippa", "text": "I can fly up high and look! Two eyes are good, but four eyes are better!", "emotion": "happy"}]},
            {"setting": "pond", "time_of_day": "day", "characters": ["Tumble", "Pippa", "Moss"], "show_prop": False, "lines": [
                {"speaker": "Moss", "text": "Hello, little friends. What are you looking for?", "emotion": "happy"},
                {"speaker": "Tumble", "text": "A red kite with blue bows on its tail!", "emotion": "neutral"},
                {"speaker": "Moss", "text": "I saw something red near the tall reeds. Let's go slowly and look together.", "emotion": "happy"}]},
            {"setting": "pond", "time_of_day": "sunset", "characters": ["Tumble", "Pippa", "Moss"], "show_prop": True, "lines": [
                {"speaker": "Pippa", "text": "One bow, two bows, three bows! It's your kite!", "emotion": "surprised"},
                {"speaker": "Tumble", "text": "You found it! Thank you, thank you!", "emotion": "happy"},
                {"speaker": "narrator", "text": "When something feels too big, it's okay to ask your friends for help. See you next time in Maple Meadow!", "emotion": "happy"}]},
        ],
    }
    prop = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 300">'
            '<path d="M150,20 L240,120 L150,220 L60,120 Z" fill="#e53935" stroke="#9a1c1a" stroke-width="10" stroke-linejoin="round"/>'
            '<path d="M150,20 V220 M60,120 H240" stroke="#ffd54f" stroke-width="10"/>'
            '<path d="M150,220 q-20,20 0,35 q20,15 0,35" stroke="#5d4037" stroke-width="5" fill="none"/>'
            '<path d="M135,245 l15,-8 l15,8 l-15,8 z M135,275 l15,-8 l15,8 l-15,8 z" fill="#42a5f5"/></svg>')
    return Episode.model_validate(data), prop


if __name__ == "__main__":
    print(json.dumps(Episode.model_json_schema(), indent=1)[:2000])
