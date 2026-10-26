"""The System Architect's stack, as a list the Developer agent must follow.

The Architect names a technology on each component of its design. The Developer agent receives these as
binding instructions and refuses (or records a deviation) when it cannot build one of them, so the code
never silently differs from the architecture that was presented.
"""

from ..models import ArchDesign

# Component type -> the role the Developer agent checks it as. Third-party and AI services are outside
# what is built, so they are left out rather than judged.
ROLE_BY_TYPE = {
    "FRONTEND": "frontend",
    "API": "backend",
    "SERVICE": "service",
    "DATABASE": "database",
    "STORAGE": "infrastructure",
    "CACHE": "infrastructure",
    "QUEUE": "infrastructure",
    "GATEWAY": "infrastructure",
}


def architecture_items(design: ArchDesign | None) -> list[dict]:
    if not design:
        return []
    items, seen = [], set()
    for component in (design.hld or {}).get("components", []):
        role = ROLE_BY_TYPE.get(component.get("type"))
        technology = (component.get("technology") or "").strip()
        if not role or not technology:
            continue
        key = (role, technology.lower(), component.get("name"))
        if key not in seen:
            seen.add(key)
            items.append({"role": role, "technology": technology, "component": component.get("name")})
    return items
