"""
augmentor/noise.py
===================
Injects realistic noise into address strings to improve model robustness.

Noise types modelled on real-world HK address problems:
  1. Abbreviation swap        九龍→KLN, 香港→HK, 新界→NT
  2. Romanization variant     彌敦道→Nathan Rd (drop "Road")
  3. Missing region prefix    Drop leading 香港/九龍/新界
  4. Separator change         號→No., 樓→/F, 室→Rm
  5. Case variation           PIONEER CENTRE, pioneer centre
  6. Extra whitespace         "Nathan  Road" (double space)
  7. Truncation               Drop floor+unit entirely

noise_rate: probability any given example gets noise applied.
Only ONE noise type is applied per example to keep labels valid.
"""

import random, re, logging
from typing import Optional

log = logging.getLogger(__name__)

REGION_ABBREVS = {
    "香港": ["HK", "H.K.", "Hong Kong"],
    "九龍": ["KLN", "Kln", "Kowloon"],
    "新界": ["NT", "N.T.", "New Territories"],
}


class NoiseInjector:
    def __init__(self, noise_rate: float = 0.2):
        self.noise_rate = noise_rate

    def inject(self, example: dict) -> Optional[dict]:
        """Return a noisy copy, or None if noise_rate not triggered."""
        if random.random() > self.noise_rate:
            return None

        address = example["address"]
        parsed  = dict(example["parsed"])  # shallow copy

        transform = random.choice([
            self._abbrev_region,
            self._abbrev_floor,
            self._abbrev_unit,
            self._drop_region,
            self._case_upper,
            self._case_lower,
            self._extra_space,
            self._drop_floor_unit,
        ])

        try:
            new_address = transform(address, parsed)
        except Exception:
            return None

        if not new_address or new_address == address:
            return None

        return {"address": new_address.strip(), "parsed": parsed, "_noisy": True}

    # ── Transform functions ────────────────────────────────────────────────
    # Each receives (address_str, parsed_dict) and returns new address_str.
    # parsed_dict can be mutated if the noise changes what's parseable.

    def _abbrev_region(self, addr: str, parsed: dict) -> str:
        for zh, alts in REGION_ABBREVS.items():
            if zh in addr:
                replacement = random.choice(alts)
                new_addr = addr.replace(zh, replacement, 1)
                # Update parsed to match
                parsed["region_zh"] = "" if replacement != zh else zh
                parsed["region_en"] = replacement
                return new_addr
        return addr

    def _abbrev_floor(self, addr: str, parsed: dict) -> str:
        # 23樓 → 23/F   or   23/F → 23F
        addr = re.sub(r"(\d+)樓", r"/F", addr)
        addr = re.sub(r"(\d+)/F", r"F", addr) if random.random() > 0.5 else addr
        return addr

    def _abbrev_unit(self, addr: str, parsed: dict) -> str:
        # 2301室 → Rm 2301   or   Room 2301 → Rm 2301
        addr = re.sub(r"(\w+)室", r"Rm ", addr)
        addr = addr.replace("Room ", "Rm ") if "Room " in addr else addr
        return addr

    def _drop_region(self, addr: str, parsed: dict) -> str:
        # Remove leading region prefix — very common in practice
        for zh in REGION_ABBREVS:
            if addr.startswith(zh):
                parsed["region_zh"] = ""
                return addr[len(zh):]
        for en in ["Hong Kong", "Kowloon", "New Territories", "HK", "KLN", "NT"]:
            if addr.endswith(f", {en}") or addr.endswith(f" {en}"):
                parsed["region_en"] = ""
                return addr[:-(len(en)+2)].rstrip(",").strip()
        return addr

    def _case_upper(self, addr: str, parsed: dict) -> str:
        return addr.upper()

    def _case_lower(self, addr: str, parsed: dict) -> str:
        return addr.lower()

    def _extra_space(self, addr: str, parsed: dict) -> str:
        # Insert a double space at a random word boundary
        words = addr.split(" ")
        if len(words) > 2:
            i = random.randint(1, len(words)-1)
            words.insert(i, "")
        return " ".join(words)

    def _drop_floor_unit(self, addr: str, parsed: dict) -> str:
        # Remove everything after the building name (floor + unit)
        # This tests model robustness to incomplete addresses
        patterns = [
            r"\d+[樓層/F]+.*$",
            r"(Room|Rm|Flat|Unit|Suite)\s*\w+.*$",
            r"\d+室.*$",
        ]
        for pat in patterns:
            new = re.sub(pat, "", addr).strip().rstrip(",").strip()
            if new and new != addr:
                parsed["floor"] = ""
                parsed["unit"]  = ""
                return new
        return addr
