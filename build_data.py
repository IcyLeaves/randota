# -*- coding: utf-8 -*-
"""Merge official hero names, OpenDota attributes, and Spectral 7-day position stats."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

ATTR = {0: "str", 1: "agi", 2: "int", 3: "all"}
ATTR_CN = {"str": "力量", "agi": "敏捷", "int": "智力", "all": "全才"}

# Spectral LRG position keys -> Dota pos 1-5
POSITION_SOURCES = [
    (1, "pos1.json", "1.1"),
    (2, "pos2.json", "1.2"),
    (3, "pos3.json", "1.3"),
    (4, "pos-off-support.json", "0.3"),
    (5, "pos4.json", "0.1"),
]

MIN_SHARE = 0.15
SOFT_SHARE = 0.12
SOFT_MATCHES = 400

# Internal npc slug -> Steam CDN react hero image slug (most match npc name)
STEAM_SLUG_MAP = {
    "antimage": "antimage",
    "nevermore": "nevermore",
    "queenofpain": "queenofpain",
    "skeleton_king": "skeleton_king",
    "obsidian_destroyer": "obsidian_destroyer",
}


def load_json(name: str):
    with (ROOT / name).open(encoding="utf-8") as f:
        return json.load(f)


def steam_slug(npc_name: str) -> str:
    slug = npc_name.replace("npc_dota_hero_", "")
    return STEAM_SLUG_MAP.get(slug, slug)


def load_spectral_active() -> dict[int, bool]:
    path = ROOT / "spectral-heroes-min.json"
    if not path.exists():
        return {}
    rows = load_json("spectral-heroes-min.json")
    return {int(h["id"]): bool(h.get("active", True)) for h in rows}


def main() -> None:
    official = load_json("dota2-herolist.json")["result"]["data"]["heroes"]
    opendota = {h["id"]: h for h in load_json("opendota-heroes.json")}
    spectral_active = load_spectral_active()

    pos_matches: dict[int, dict[int, int]] = {}
    for pos, filename, key in POSITION_SOURCES:
        raw = load_json(filename)
        table = raw.get("result", {}).get(key, {})
        for hero_id, stats in table.items():
            hid = int(hero_id)
            matches = int(stats.get("matches_s") or 0)
            pos_matches.setdefault(hid, {})[pos] = matches

    heroes = []
    for h in official:
        hid = h["id"]
        if spectral_active and spectral_active.get(hid) is False:
            continue
        od = opendota.get(hid, {})
        slug = steam_slug(h["name"])
        attr = ATTR.get(h.get("primary_attr"), od.get("primary_attr", "all"))
        attack = od.get("attack_type", "Melee")
        roles = od.get("roles", [])

        counts = pos_matches.get(hid, {})
        total = sum(counts.values())
        positions = []
        if total:
            top = max(counts.values())
            for pos in range(1, 6):
                n = counts.get(pos, 0)
                if n <= 0:
                    continue
                share = n / total
                if n == top or share >= MIN_SHARE or (share >= SOFT_SHARE and n >= SOFT_MATCHES):
                    positions.append(pos)
        if not positions:
            roles_l = {r.lower() for r in roles}
            if "carry" in roles_l:
                positions.append(1)
            if "nuker" in roles_l and "carry" in roles_l:
                positions.append(2)
            if "initiator" in roles_l or "durable" in roles_l:
                positions.append(3)
            if "support" in roles_l:
                positions.extend([4, 5])
            positions = sorted(set(positions)) or [1]

        heroes.append(
            {
                "id": hid,
                "slug": slug,
                "name": h["name_loc"],
                "nameEn": h["name_english_loc"],
                "attr": attr,
                "attrCn": ATTR_CN[attr],
                "attack": "近战" if attack == "Melee" else "远程",
                "complexity": h.get("complexity", 1),
                "roles": roles,
                "positions": positions,
                "avatar": (
                    "https://cdn.cloudflare.steamstatic.com/apps/dota2/images/"
                    f"dota_react/heroes/{slug}.png"
                ),
                "icon": (
                    "https://cdn.cloudflare.steamstatic.com/apps/dota2/images/"
                    f"dota_react/heroes/icons/{slug}.png"
                ),
            }
        )

    heroes.sort(key=lambda x: x["id"])
    out = ROOT / "heroes-data.js"
    payload = json.dumps(heroes, ensure_ascii=False, indent=2)
    out.write_text(f"window.HEROES = {payload};\n", encoding="utf-8")

    print(f"heroes: {len(heroes)}")
    samples = {1: "敌法师", 2: "祈求者", 3: "斧王", 4: "撼地者", 5: "水晶室女"}
    by_name = {h["name"]: h for h in heroes}
    for pos, name in samples.items():
        h = by_name.get(name)
        if h:
            print(f"  {name}: pos {h['positions']}")
    counts = {p: sum(1 for h in heroes if p in h["positions"]) for p in range(1, 6)}
    print("pool by position:", counts)


if __name__ == "__main__":
    main()
