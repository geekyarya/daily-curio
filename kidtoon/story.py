"""Episode + Short scripts: schema, writing, validation and kid-safety review."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

CastName = Literal["Tumble", "Pippa", "Moss"]
Speaker = Literal["narrator", "Tumble", "Pippa", "Moss"]
Camera = Literal["zoom_in", "zoom_out", "pan_left", "pan_right", "pan_up", "pan_down", "still"]
Effect = Literal["none", "sparkles", "snow", "leaves", "bubbles", "rain", "fireflies", "petals"]


class Line(BaseModel):
    speaker: Speaker
    text: str


class Shot(BaseModel):
    visual: str
    characters: list[CastName]
    camera: Camera
    effect: Effect
    lines: list[Line]


class Short(BaseModel):
    title: str
    description: str
    shots: list[Shot]


class Episode(BaseModel):
    title: str
    description: str
    tags: list[str]
    lesson: str
    thumbnail_visual: str
    thumbnail_characters: list[CastName]
    shots: list[Shot]
    short: Short


class Review(BaseModel):
    approved: bool
    issues: list[str]


SAFETY_RULES = """\
- Gentle, warm and positive. No violence, scary peril, villains, weapons, injuries, death, unresolved bullying, or frightening imagery.
- No unsafe behaviour a child could copy (climbing high, fire, eating unknown plants or berries, swimming alone, talking to strangers, wandering off alone).
- No brands, real people, existing cartoon characters or franchises, products, links, or asking viewers to subscribe/like/comment/buy (YouTube Made-for-Kids rules).
- No requests for personal information. No romance, gross-out humour, rude words or sarcasm.
- Vocabulary right for ages {age}; short sentences; one clear, kind lesson.
- Facts about animals, nature, numbers and colours must be correct."""


def words(shots: list[Shot]) -> int:
    return sum(len(l.text.split()) for s in shots for l in s.lines)


def repair(ep: Episode) -> None:
    """Fix small slips in place instead of spending a whole rewrite on them."""
    for s in ep.shots + ep.short.shots:
        s.characters = list(dict.fromkeys(s.characters))
        for l in s.lines:
            if l.speaker != "narrator" and l.speaker not in s.characters and len(s.characters) < 3:
                s.characters.append(l.speaker)
        s.lines = [l for l in s.lines if l.text.strip()]
    for name in ep.thumbnail_characters[3:]:
        ep.thumbnail_characters.remove(name)


def validate(ep: Episode, cfg: dict) -> list[str]:
    p: list[str] = []
    target = cfg["episode_minutes"] * 140
    w = words(ep.shots)
    if not 0.75 * target <= w <= 1.3 * target:
        p.append(f"The episode must have about {target} spoken words in total; it has {w}.")
    if not 14 <= len(ep.shots) <= 45:
        p.append(f"The episode needs 18-35 shots; it has {len(ep.shots)}.")
    sw = words(ep.short.shots)
    max_w = int(cfg["short_seconds"] * 2.3)
    if not 40 <= sw <= max_w:
        p.append(f"The short must have 40-{max_w} spoken words; it has {sw}.")
    if not 3 <= len(ep.short.shots) <= 8:
        p.append("The short needs 4-7 shots.")
    for name, shots in (("episode", ep.shots), ("short", ep.short.shots)):
        for i, s in enumerate(shots, 1):
            if len(s.characters) > 3 or len(set(s.characters)) != len(s.characters):
                p.append(f"{name} shot {i}: list at most 3 distinct characters.")
            for l in s.lines:
                if l.speaker != "narrator" and l.speaker not in s.characters:
                    p.append(f"{name} shot {i}: {l.speaker} speaks but is not in `characters`.")
            if not s.lines:
                p.append(f"{name} shot {i}: every shot needs at least one line.")
    if len(ep.title) > 90 or len(ep.short.title) > 80:
        p.append("Titles are too long.")
    return p


def write_episode(cfg: dict, history: list[dict], llm, log=print) -> Episode:
    age = cfg["audience_age"]
    rules = SAFETY_RULES.format(age=age)
    cast = "\n".join(f"- {n}: {c['look']}. Personality: {c['personality']}." for n, c in cfg["cast"].items())
    recent = "\n".join(f"- {h['title']} (lesson: {h['lesson']})" for h in history[-60:]) or "- (none yet)"
    minutes = cfg["episode_minutes"]

    system = f"""You are the head writer and storyboard artist of "{cfg['channel_name']}", an original animated
YouTube show for children aged {age}, told as a beautifully illustrated storybook with narration and character voices.

Recurring cast (the only named characters; background animals without names are fine in visuals):
{cast}

Each episode is a cosy, self-contained adventure with a clear beginning, a small gentle problem, a few attempts,
a happy resolution and one kind, practical lesson (sharing, patience, trying again, feelings, helping, counting,
colours, shapes, seasons, nature facts...). Use gentle repetition, sound words (whoosh! splash!), a little rhyme or
counting where it fits, and moments that invite the child to answer ("Can you count them with me?").
The narrator closes by restating the lesson warmly and saying goodbye until next time.

Hard rules:
{rules}"""

    prompt = f"""Write a new episode about {minutes} minutes long (~{minutes * 140} spoken words) as a storyboard of
20-30 shots, PLUS a separate vertical YouTube Short (~{cfg['short_seconds']} seconds, ~{int(cfg['short_seconds'] * 2)} words,
4-6 shots) that retells the funniest or sweetest moment of the episode as a complete mini-story with a hook in the first line.

Recent episodes - do not repeat their plots or lessons:
{recent}

Field guide:
- visual: a self-contained illustration brief for that shot: where we are, what each character is doing and feeling,
  key objects, composition and framing (wide / medium / close-up), time of day. Describe characters by name; an
  illustrator will keep their designs consistent. Never put text, signs or letters in images. Short shots are
  vertical (portrait) images, so compose them tall.
- characters: who is visible in the shot (0-3). Anyone who speaks must be visible.
- camera: slow camera move for the shot. Vary it; use "still" rarely.
- effect: a gentle animated overlay that suits the shot ("none" is fine).
- lines: 1-5 lines per shot, each one or two short sentences.
- thumbnail_visual: an eye-catching, expressive close-up moment for the video thumbnail (no text).
- tags: 10-15 search tags. title: one catchy, clear title under 70 characters (no "|" or subtitles), no clickbait.
- description: 2-4 sentences for parents."""

    feedback = ""
    problems: list[str] = []
    for attempt in range(1, 5):
        log(f"  writing (attempt {attempt})")
        ep = llm.json(system, prompt + feedback, Episode)
        repair(ep)
        problems = validate(ep, cfg)
        if not problems:
            review = review_episode(llm, ep, rules, age)
            if review.approved:
                log(f"  approved: {ep.title!r} ({len(ep.shots)} shots, {words(ep.shots)} words)")
                return ep
            problems = review.issues or ["Reviewer rejected the script."]
            log(f"  safety review: {problems}")
        else:
            log(f"  validation: {problems}")
        feedback = "\n\nYour previous draft was rejected. Write a complete NEW draft fixing:\n- " + "\n- ".join(problems)
    raise RuntimeError(f"No approved episode after retries: {problems}")


def review_episode(llm, ep: Episode, rules: str, age: str) -> Review:
    system = (f"You are a strict children's-media standards reviewer for a YouTube channel for ages {age}. "
              "Approve only scripts that meet every rule. Be concrete and actionable about any issue.")
    prompt = (f"Rules:\n{rules}\n\nScript and storyboard (JSON):\n{ep.model_dump_json(indent=1)}\n\n"
              "Check titles, descriptions, tags, every line and every visual (images must not be scary or unsafe). "
              "approved=false if anything breaks a rule. If approved, issues must be empty.")
    return llm.json(system, prompt, Review, temperature=0.2)
