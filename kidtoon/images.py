"""Free image generation.

Providers, tried in order (config.image.providers):
  cloudflare_flux2   FLUX.2 [klein] on Cloudflare Workers AI. Takes the cast reference sheets as input images,
                     so characters look the same in every shot. Free: 10,000 neurons/day (~60-80 images).
  cloudflare_schnell FLUX.1 schnell on Workers AI: cheaper, text-only (no reference images).
  pollinations       gen.pollinations.ai with POLLINATIONS_API_KEY, or the anonymous classic endpoint
                     (slow: one image per ~45s, lower quality, watermark cropped off).
"""
from __future__ import annotations

import base64
import io
import os
import time
import urllib.parse
from pathlib import Path

import requests
from PIL import Image

CF_URL = "https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/{model}"


class ImageGen:
    def __init__(self, cfg: dict, cast_dir: Path, log=print):
        self.cfg, self.cast_dir, self.log = cfg, cast_dir, log
        self.style = cfg["image"]["style"]
        self.providers = [p for p in cfg["image"]["providers"] if self._available(p)]
        if not self.providers:
            raise RuntimeError("No image provider configured: set the CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN secrets")
        self.dead: set[str] = set()
        self.count = 0

    @staticmethod
    def _available(p: str) -> bool:
        if p.startswith("cloudflare"):
            return bool(os.environ.get("CLOUDFLARE_API_TOKEN") and cloudflare_account_id())
        if p == "pollinations":  # the anonymous endpoint is only used for --demo previews
            return bool(os.environ.get("POLLINATIONS_API_KEY") or os.environ.get("KIDTOON_ALLOW_ANON"))
        return True

    # ------------------------------------------------------------------ public
    def generate(self, prompt: str, size: tuple[int, int], refs: list[str], seed: int, out: Path) -> Path:
        if out.exists():
            return out
        full = self._prompt(prompt, refs)
        for p in self.providers:
            if p in self.dead:
                continue
            for attempt in range(3):
                try:
                    img = getattr(self, f"_{p}")(full, size, refs, (seed + attempt) % 2_000_000_000)
                    img = cover(img.convert("RGB"), size)
                    img.save(out, quality=94)
                    self.count += 1
                    return out
                except QuotaError as e:
                    self.log(f"    {p}: quota/limit reached ({e}); switching provider")
                    self.dead.add(p)
                    break
                except Exception as e:  # noqa: BLE001
                    self.log(f"    {p}: {e}")
                    time.sleep(5 * (attempt + 1))
        raise RuntimeError(f"All image providers failed for: {prompt[:80]}")

    def ensure_cast(self) -> None:
        """Create a reference sheet for each character once; reuse forever (replace the PNGs to redesign)."""
        self.cast_dir.mkdir(parents=True, exist_ok=True)
        for name, c in self.cfg["cast"].items():
            out = self.cast_dir / f"{name}.png"
            if out.exists():
                continue
            self.log(f"  designing {name}")
            prompt = (f"{self.style}. Character design reference sheet of {name}, {c['look']}. Full body, standing, "
                      "facing the viewer with a friendly smile, centered, simple plain cream background. "
                      "Exactly one single character in one pose: no extra views, no turnaround, no small copies, "
                      "nothing else in the picture.")
            tmp = out.with_suffix(".jpg")
            self.generate(prompt, (768, 768), [], seed=sum(map(ord, name)), out=tmp)
            Image.open(tmp).save(out)
            tmp.unlink()

    # ------------------------------------------------------------------ helpers
    def _prompt(self, prompt: str, refs: list[str]) -> str:
        if not refs:
            return f"{self.style}. {prompt}"
        looks = "; ".join(f"{n} is {self.cfg['cast'][n]['look']} (exactly as in reference image {i + 1})"
                          for i, n in enumerate(refs))
        return (f"{self.style}. {prompt}. Characters: {looks}. Keep every character's design, colours and "
                "proportions identical to their reference image; do not copy the reference backgrounds.")

    def _ref_bytes(self, name: str) -> bytes:
        img = Image.open(self.cast_dir / f"{name}.png").convert("RGB")
        img.thumbnail((512, 512))
        buf = io.BytesIO()
        img.save(buf, "PNG")
        return buf.getvalue()

    def _cf(self, model: str, **kw) -> requests.Response:
        url = CF_URL.format(acct=cloudflare_account_id(), model=model)
        r = requests.post(url, headers={"Authorization": f"Bearer {os.environ['CLOUDFLARE_API_TOKEN']}"},
                          timeout=180, **kw)
        if r.status_code == 429 or (r.status_code >= 400 and "neuron" in r.text.lower()):
            raise QuotaError(r.text[:200])
        if r.status_code >= 400:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
        return r

    @staticmethod
    def _decode_cf(r: requests.Response) -> Image.Image:
        if r.headers.get("content-type", "").startswith("image/"):
            return Image.open(io.BytesIO(r.content))
        data = r.json()
        b64 = (data.get("result") or data).get("image")
        if not b64:
            raise RuntimeError(f"no image in response: {str(data)[:200]}")
        return Image.open(io.BytesIO(base64.b64decode(b64)))

    # ------------------------------------------------------------------ providers
    def _cloudflare_flux2(self, prompt, size, refs, seed):
        files = {"prompt": (None, prompt), "width": (None, str(size[0])), "height": (None, str(size[1])),
                 "seed": (None, str(seed))}
        for i, n in enumerate(refs[:4]):
            files[f"input_image_{i}"] = (f"{n}.png", self._ref_bytes(n), "image/png")
        return self._decode_cf(self._cf("@cf/black-forest-labs/flux-2-klein-4b", files=files))

    def _cloudflare_schnell(self, prompt, size, refs, seed):
        # schnell is square-ish and text-only; ask for the long side and crop to shape
        r = self._cf("@cf/black-forest-labs/flux-1-schnell", json={"prompt": prompt[:2000], "steps": 8, "seed": seed})
        return self._decode_cf(r)

    def _pollinations(self, prompt, size, refs, seed):
        key = os.environ.get("POLLINATIONS_API_KEY")
        q = urllib.parse.quote(prompt[:1500])
        w, h = size
        if key:
            url = f"https://gen.pollinations.ai/image/{q}?width={w}&height={h}&seed={seed}&model=flux&nologo=true"
            r = requests.get(url, headers={"Authorization": f"Bearer {key}"}, timeout=180)
        else:
            scale = (768 * 768 / (w * h)) ** 0.5  # anonymous endpoint caps area at 768x768
            url = (f"https://image.pollinations.ai/prompt/{q}?width={int(w * scale)}&height={int(h * scale)}"
                   f"&seed={seed}&nologo=true")
            time.sleep(46)  # anonymous limit: one image per ~45 seconds
            r = requests.get(url, timeout=180)
        if r.status_code in (401, 402, 429):
            raise QuotaError(f"HTTP {r.status_code}")
        if r.status_code >= 400 or not r.headers.get("content-type", "").startswith("image/"):
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:700]}")
        img = Image.open(io.BytesIO(r.content)).convert("RGB")
        if not key:  # crop the corner watermark
            img = img.crop((0, 0, img.width, int(img.height * 0.93)))
        return img


class QuotaError(RuntimeError):
    pass


def cloudflare_account_id() -> str:
    """CLOUDFLARE_ACCOUNT_ID if set, otherwise the account the API token belongs to."""
    acct = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    if acct or not token:
        return acct
    try:
        r = requests.get("https://api.cloudflare.com/client/v4/accounts",
                         headers={"Authorization": f"Bearer {token}"}, timeout=30)
        accounts = r.json().get("result") or []
        if accounts:
            acct = accounts[0]["id"]
            os.environ["CLOUDFLARE_ACCOUNT_ID"] = acct
            print(f"  using Cloudflare account {accounts[0].get('name', '')} (looked up from the token)", flush=True)
        else:
            print(f"  could not look up the Cloudflare account from the token: {r.text[:200]}", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"  Cloudflare account lookup failed: {e}", flush=True)
    return acct


def cover(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Scale and centre-crop to exactly `size`."""
    w, h = size
    s = max(w / img.width, h / img.height)
    img = img.resize((max(w, round(img.width * s)), max(h, round(img.height * s))), Image.LANCZOS)
    x, y = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((x, y, x + w, y + h))
