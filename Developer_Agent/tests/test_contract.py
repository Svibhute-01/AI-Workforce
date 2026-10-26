import sys

import pytest

from app.stacks import STACKS, check_contract, contract_text, get_stack, rules_for
from app.tools.runner import LocalRunner

# What the Architect's own default stack produces for a typical project.
TRACKIFY = [
    {"role": "frontend", "technology": "React (Vite) with Tailwind CSS", "component": "Web App"},
    {"role": "backend", "technology": "Python with FastAPI and SQLAlchemy", "component": "API"},
    {"role": "database", "technology": "PostgreSQL", "component": "Database"},
]


def test_react_and_tailwind_are_refused_even_though_the_text_contains_css():
    result = check_contract(get_stack("python-fastapi"), TRACKIFY)
    assert result["unsupported"] == ["frontend - Web App: React (Vite) with Tailwind CSS"]


def test_the_supported_stack_passes_with_nothing_dropped():
    items = [
        {"role": "frontend", "technology": "Server-rendered HTML with Jinja2, plain CSS and JavaScript", "component": "Pages"},
        {"role": "backend", "technology": "Python with FastAPI and SQLAlchemy", "component": "API"},
        {"role": "database", "technology": "PostgreSQL", "component": "Database"},
    ]
    assert check_contract(get_stack("python-fastapi"), items) == {"unsupported": [], "notes": []}


@pytest.mark.parametrize("role, technology", [
    ("backend", "Django"), ("backend", "Node.js with Express"), ("backend", "Java Spring Boot"),
    ("database", "MongoDB"), ("database", "MySQL"), ("frontend", "Vue 3"), ("frontend", "Angular"),
    ("backend", "Something unknown"),
])
def test_other_technologies_are_never_silently_replaced(role, technology):
    result = check_contract(get_stack("python-fastapi"), [{"role": role, "technology": technology, "component": "X"}])
    assert len(result["unsupported"]) == 1


def test_each_stack_judges_by_its_own_capabilities():
    express = [{"role": "backend", "technology": "Node.js with Express", "component": "API"}]
    assert check_contract(get_stack("node-express"), express)["unsupported"] == []
    assert check_contract(get_stack("python-fastapi"), express)["unsupported"] != []
    postgres = [{"role": "database", "technology": "PostgreSQL", "component": "DB"}]
    assert check_contract(get_stack("node-express"), postgres)["unsupported"] != []   # honest: no driver in that profile
    assert check_contract(get_stack("static-html"), [{"role": "backend", "technology": "FastAPI", "component": "API"}])["unsupported"]


def test_infrastructure_is_reported_as_a_note_not_hidden():
    result = check_contract(get_stack("python-fastapi"), [{"role": "infrastructure", "technology": "Redis cache", "component": "Cache"}])
    assert result["unsupported"] == [] and "Redis cache" in result["notes"][0]


def test_components_without_a_technology_are_ignored():
    assert check_contract(get_stack("python-fastapi"), [{"role": "backend", "technology": None, "component": "API"}]) == {"unsupported": [], "notes": []}


def test_the_prompt_carries_the_architecture_and_the_unbuildable_parts():
    text = contract_text(TRACKIFY, ["frontend - Web App: React (Vite) with Tailwind CSS"])
    assert "follow it exactly" in text and "PostgreSQL" in text and "could NOT build" in text and "React" in text
    assert contract_text([], []) == ""


def test_python_rules_target_the_architects_database_and_forbid_frameworks():
    rules = rules_for(get_stack("python-fastapi"))
    assert "DATABASE_URL" in rules and "psycopg[binary]" in rules and "postgresql+psycopg" in rules
    assert "Do not use React" in rules


def test_checks_and_previews_run_with_sqlite_while_the_code_defaults_to_the_architects_database(tmp_path):
    runner = LocalRunner(tmp_path, get_stack("python-fastapi"))
    result = runner._execute("probe", [sys.executable, "-c", "import os; print(os.environ.get('DATABASE_URL'))"], 30)
    assert result.stdout.strip() == "sqlite:///./app.db"
    assert get_stack("python-fastapi").check_env == {"DATABASE_URL": "sqlite:///./app.db"}
    assert STACKS["node-express"].check_env == {}


@pytest.mark.parametrize("technology", [
    "Plain JavaScript", "JavaScript and HTML", "Server-rendered HTML with Jinja2, plain CSS and JavaScript",
    "Trusted templates in HTML", "Invite page in HTML",
])
def test_unbuildable_words_must_match_whole_words(technology):
    result = check_contract(get_stack("python-fastapi"), [{"role": "frontend", "technology": technology, "component": "UI"}])
    assert result["unsupported"] == []


@pytest.mark.parametrize("technology", ["Java", "Java Spring Boot", "React.js", "Vue", "Rust", "C#", ".NET 8", "Next.js"])
def test_whole_word_matching_still_catches_the_real_thing(technology):
    result = check_contract(get_stack("python-fastapi"), [{"role": "backend", "technology": technology + " and Python", "component": "X"}])
    assert len(result["unsupported"]) == 1


def test_an_internal_service_is_only_refused_for_unbuildable_technology():
    stack = get_stack("python-fastapi")
    assert check_contract(stack, [{"role": "service", "technology": "SendGrid email provider", "component": "Mailer"}])["unsupported"] == []
    assert check_contract(stack, [{"role": "service", "technology": "Java Spring service", "component": "Billing"}])["unsupported"]
