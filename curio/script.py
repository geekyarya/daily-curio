"""Video scripts: schema, writing with Gemini, validation, and an accuracy + standards review."""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel

Camera = Literal["zoom_in", "zoom_out", "pan_left", "pan_right", "pan_up", "pan_down", "still"]
Effect = Literal["none", "dust", "embers", "snow", "rain", "fireflies", "sparkles", "leaves", "bubbles"]


class Shot(BaseModel):
    card: str          # on-screen title for the start of a list item / chapter, else ""
    visual: str
    camera: Camera
    effect: Effect
    narration: str


class Short(BaseModel):
    title: str
    description: str
    shots: list[Shot]


class Video(BaseModel):
    title: str
    description: str
    tags: list[str]
    thumbnail_visual: str
    thumbnail_text: str
    shots: list[Shot]
    short: Short


class Review(BaseModel):
    approved: bool
    issues: list[str]


RULES = """\
Accuracy (most important):
- Use only well-documented facts that reputable encyclopedias and historians agree on.
- Never present a popular myth as true (e.g. Vikings' horned helmets, Napoleon being unusually short). Busting a myth is fine if you say so clearly.
- Mark genuinely disputed points as such ("historians still debate...", "according to legend...").
- Avoid precise numbers, dates or quotes unless you are certain; prefer "around", "about". No invented quotes.
Standards:
- Treat wars, disasters, slavery, disease and death with respect: no gore, no graphic violence, no sensationalism.
- No hate, slurs, stereotypes or mocking of any group, religion or nationality. No partisan politics about living people.
- No medical, legal or financial advice; no dangerous instructions.
- Images: no living real people, no graphic injury, no hate symbols, no text in images."""


def words(shots: list[Shot]) -> int:
    return sum(len(s.narration.split()) for s in shots)


def repair(v: Video) -> None:
    for shots in (v.shots, v.short.shots):
        shots[:] = [s for s in shots if s.narration.strip()]
        for s in shots:
            s.card = s.card.strip()
            s.narration = re.sub(r"\s+", " ", s.narration).strip()
    v.thumbnail_text = " ".join(v.thumbnail_text.split()[:5])


def validate(v: Video, fmt: str, cfg: dict) -> list[str]:
    spec = cfg["format_specs"][fmt]
    p: list[str] = []
    w = words(v.shots)
    if not 0.8 * spec["words"] <= w <= 1.3 * spec["words"]:
        p.append(f"The narration must total about {spec['words']} words; it has {w}.")
    lo, hi = (int(x) for x in spec["shots"].split("-"))
    if not lo - 4 <= len(v.shots) <= hi + 6:
        p.append(f"Use {spec['shots']} shots; there are {len(v.shots)}.")
    cards = [s.card for s in v.shots if s.card]
    if spec["items"] and len(cards) != spec["items"]:
        p.append(f"Exactly {spec['items']} shots must have a `card` (one per list item, counting down); found {len(cards)}.")
    long = [i + 1 for i, s in enumerate(v.shots) if len(s.narration.split()) > 75]
    if long:
        p.append(f"Shots {long} have more than 75 words of narration; split them into more shots.")
    sw = words(v.short.shots)
    max_w = int(cfg["short_seconds"] * 2.5)
    if not 50 <= sw <= max_w:
        p.append(f"The Short must have 50-{max_w} narration words; it has {sw}.")
    if not 3 <= len(v.short.shots) <= 8:
        p.append("The Short needs 4-7 shots.")
    if len(v.title) > 90 or len(v.short.title) > 80:
        p.append("Titles are too long.")
    return p


def write_video(cfg: dict, history: list[dict], fmt: str, category: str, topic: str, llm, log=print) -> Video:
    spec = cfg["format_specs"][fmt]
    recent = "\n".join(f"- {h['title']}" for h in history[-120:]) or "- (none yet)"
    subject = f'The topic is: "{topic}".' if topic else f"Pick a fresh, specific, clickable topic within: {category}."

    system = f"""You are the head writer of "{cfg['channel_name']}", a YouTube channel for {cfg['audience']} that posts
history stories and "top 5 / top 10" fact videos about history and everyday life. The voice is a warm, witty,
confident British documentary narrator: vivid, clear, surprising, never dry, never clickbait-dishonest.

{RULES}

Retention craft: open with a strong hook in the first 2 sentences (a surprising claim or question that the video
pays off), keep every sentence concrete, end each list item or chapter with a smooth bridge to the next, and save
the most surprising item for last. Close with a short recap, ask viewers which fact surprised them most in the
comments, and invite them to subscribe for a new video every day."""

    if spec["items"]:
        shape = (f"a {spec['label']} counting down from #{spec['items']} to #1. Start with 1-2 hook/intro shots "
                 f"(card \"\"), then each item: its first shot has card like \"#7 · The Emperor Who Fought the Sea\" "
                 f"(number, a middle dot, a short punchy heading), followed by 1-3 more shots with card \"\". "
                 f"End with 1-2 outro shots (card \"\").")
    else:
        shape = ("a history story in 4-6 chapters. Start with 1-2 hook shots (card \"\"); the first shot of each chapter "
                 "has a card like \"Part 2 · The Night of the Fire\"; end with 1-2 outro shots (card \"\").")

    prompt = f"""{subject}
Write {shape}
Length: about {spec['words']} narration words in {spec['shots']} shots (roughly 10-25 seconds of narration each).

Also write a vertical YouTube Short (~{cfg['short_seconds']} seconds, about {int(cfg['short_seconds'] * 2.2)} words,
4-6 shots, all cards "") built around the single most surprising fact from the video, opening with an instant hook.

Recent videos - do not repeat these topics:
{recent}

Field guide:
- visual: a self-contained illustration brief for that moment: subject, setting, era-accurate clothing/architecture,
  composition and lighting. No text or lettering in the image. No living real people. Short visuals are vertical
  (portrait), so compose them tall.
- camera: slow camera move; vary it. effect: subtle animated overlay that suits the mood ("none" is common;
  "dust" for old interiors, "embers" for fire/battles/forges, "snow"/"rain" for weather, "fireflies" for night).
- narration: what the narrator says during the shot.
- title: curiosity-driven and accurate, under 70 characters (e.g. "10 Weird Things Romans Did Every Day").
- thumbnail_text: 2-4 punchy words for the thumbnail (e.g. "ROME WAS WEIRD"). thumbnail_visual: one striking image.
- description: 2-4 sentences, then a blank line and 3 relevant hashtags. tags: 12-18 search tags."""

    feedback, problems = "", []
    for attempt in range(1, 5):
        log(f"  writing (attempt {attempt})")
        v = llm.json(system, prompt + feedback, Video)
        repair(v)
        problems = validate(v, fmt, cfg)
        if not problems:
            review = review_video(llm, v, cfg)
            if review.approved:
                log(f"  approved: {v.title!r} ({len(v.shots)} shots, {words(v.shots)} words)")
                return v
            problems = review.issues or ["Reviewer rejected the script."]
            log(f"  review: {problems}")
        else:
            log(f"  validation: {problems}")
        feedback = "\n\nYour previous draft was rejected. Write a complete NEW draft fixing:\n- " + "\n- ".join(problems)
    raise RuntimeError(f"No approved script after retries: {problems}")


def review_video(llm, v: Video, cfg: dict) -> Review:
    system = ("You are a meticulous fact-checker and standards editor for an educational YouTube channel. "
              "Check every factual claim against well-established historical and scientific consensus.")
    prompt = (f"Rules:\n{RULES}\n\nScript (JSON):\n{v.model_dump_json(indent=1)}\n\n"
              "Reject (approved=false) if ANY claim is false, a myth stated as fact, an invented quote, an overly precise "
              "number you cannot stand behind, or anything breaking the standards. List each problem with the exact "
              "sentence and the correction. If approved, issues must be empty.")
    return llm.json(system, prompt, Review, temperature=0.1)
