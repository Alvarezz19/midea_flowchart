from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import TabModel


@dataclass
class DomainProfile:
    name: str
    raw: dict[str, Any]

    @property
    def tab_roles(self) -> list[dict[str, Any]]:
        return list(self.raw.get("tab_roles", []))

    @property
    def point_groups(self) -> list[dict[str, Any]]:
        return list(self.raw.get("point_groups", []))


def load_profiles(profiles_dir: Path) -> list[DomainProfile]:
    profiles: list[DomainProfile] = []
    for path in sorted(profiles_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        profiles.append(DomainProfile(name=data["name"], raw=data))
    return profiles


def detect_profile(source_path: Path, tabs: dict[str, TabModel], profiles: list[DomainProfile]) -> DomainProfile | None:
    if not profiles:
        return None

    source_text = str(source_path).lower()
    labels = [tab.label for tab in tabs.values()]
    best_profile: DomainProfile | None = None
    best_score = -1

    for profile in profiles:
        score = 0
        for keyword in profile.raw.get("family_keywords", []):
            if str(keyword).lower() in source_text:
                score += 5
        for keyword in profile.raw.get("file_keywords", []):
            if str(keyword).lower() in source_text:
                score += 8
        for role in profile.tab_roles:
            tokens = [str(item) for item in role.get("contains", [])]
            if any(_contains_all(label, tokens) for label in labels):
                score += 3
        if score > best_score:
            best_profile = profile
            best_score = score

    return best_profile if best_score > 0 else None


def assign_tab_roles(tabs: dict[str, TabModel], profile: DomainProfile | None) -> None:
    if profile is None:
        return

    for tab in tabs.values():
        for role in profile.tab_roles:
            tokens = [str(item) for item in role.get("contains", [])]
            if _contains_all(tab.label, tokens):
                tab.role = str(role.get("role", "unknown_tab"))
                break


def classify_point_group(name: str, profile: DomainProfile | None) -> str:
    if profile is None:
        return "未归类"

    normalized = name.upper()
    for group in profile.point_groups:
        prefixes = [str(item).upper() for item in group.get("prefixes", [])]
        keywords = [str(item) for item in group.get("keywords", [])]
        if any(normalized.startswith(prefix) for prefix in prefixes):
            return str(group.get("label", "未归类"))
        if any(keyword and keyword in name for keyword in keywords):
            return str(group.get("label", "未归类"))
    return "未归类"


def _contains_all(text: str, tokens: list[str]) -> bool:
    return all(token in text for token in tokens)
