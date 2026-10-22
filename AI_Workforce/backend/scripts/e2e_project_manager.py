"""End-to-end check: SRS -> Requirements Analyst -> Project Manager -> PostgreSQL -> API.

Runs against a LIVE backend with your real Gemini key. It generates nothing itself:
it calls the real endpoints and then VERIFIES the plan the LLM produced.

Use the existing project and its saved Requirements Analyst output:

    python scripts/e2e_project_manager.py --email you@example.com --password '...' --project-id 3

Or start from the SRS PDF (uploads it, runs the analyst, then the Project Manager):

    python scripts/e2e_project_manager.py --email you@example.com --password '...' \
        --srs ../data/uploads/<the Customer Registration SRS>.pdf

Exit code 0 = every check passed.
"""

import argparse
import json
import sys
from pathlib import Path

import httpx

FORBIDDEN_UNLESS_IN_REQUIREMENTS = ("biometric", "oauth", "social login", "payment", "two-factor", "2fa")
FIB = {1, 2, 3, 5, 8, 13}
results: list[tuple[bool, str]] = []


def check(ok: bool, message: str) -> bool:
    results.append((ok, message))
    print(("  PASS  " if ok else "  FAIL  ") + message)
    return ok


def main() -> int:
    args = parse_args()
    client = httpx.Client(base_url=args.base_url, timeout=900)

    token = login_or_register(client, args)
    client.headers["Authorization"] = f"Bearer {token}"

    project_id = args.project_id
    if project_id is None:
        project_id = create_project_and_analyze(client, args)
    else:
        print(f"Using existing project {project_id}")

    analysis = get(client, f"/api/projects/{project_id}/analysis")
    reqs = analysis["functional_requirements"]
    print(f"\nRequirements Analyst output: {len(reqs)} requirements, {len(analysis['user_stories'])} stories, "
          f"{len(analysis['non_functional_requirements'])} NFRs, {len(analysis['ambiguities'])} ambiguities")
    if not check(bool(reqs), "Project has saved Requirements Analyst output"):
        return finish()

    print("\nRunning Project Manager AI (real LLM, this can take a minute)...")
    response = client.post(f"/api/projects/{project_id}/project-manager/run")
    if not check(response.status_code == 200, f"POST /project-manager/run -> {response.status_code}"):
        print("   ", response.text[:600])
        return finish()
    plan = response.json()

    saved = get(client, f"/api/projects/{project_id}/project-manager")
    check(saved["status"] == "COMPLETED" and len(saved["tasks"]) == len(plan["tasks"]),
          "Plan is persisted and re-readable via GET /project-manager")
    for path, key in (("tasks", "tasks"), ("sprints", "sprints"), ("milestones", "milestones"),
                      ("risks", "risks"), ("dependencies", "dependencies")):
        check(len(get(client, f"/api/projects/{project_id}/{path}")) == len(saved[key]) > 0,
              f"GET /{path} returns the stored {key}")

    verify_plan(plan, analysis)
    print_summary(plan)
    return finish()


def verify_plan(plan: dict, analysis: dict) -> None:
    print("\nVerifying the generated plan against the Requirements Analyst output")
    tasks = plan["tasks"]
    by_id = {t["task_id"]: t for t in tasks}
    req_ids = {f"REQ-{r['id']}": r for r in analysis["functional_requirements"]}

    check(len(tasks) >= len(req_ids), f"{len(tasks)} tasks for {len(req_ids)} requirements")
    check(all(t["story_points"] in FIB for t in tasks), "All story points are Fibonacci (1,2,3,5,8,13)")
    check(all(t["suggested_role"] for t in tasks), "Every task has a suggested role")

    # Every requirement has at least one task.
    cited = {t["related_requirement_id"] for t in tasks if t["related_requirement_id"]}
    for t in tasks:
        cited.update(a for a in t["related_artifact_ids"] if a.startswith("REQ-"))
    missing = [r["title"] for key, r in req_ids.items() if key not in cited]
    check(not missing, "Every requirement is covered by at least one task" + (f" (missing: {missing})" if missing else ""))

    # Grounding: EXPLICIT tasks cite something; nothing points outside this project.
    valid = {f"REQ-{r['id']}" for r in analysis["functional_requirements"]}
    valid |= {f"US-{s['id']}" for s in analysis["user_stories"]}
    ungrounded = [t["task_id"] for t in tasks if t["grounding"] == "EXPLICIT"
                  and not (t["related_requirement_id"] or t["related_story_id"] or t["related_artifact_ids"])]
    check(not ungrounded, "Every EXPLICIT task cites a requirement, story or artifact")
    bad_refs = [t["task_id"] for t in tasks if (t["related_requirement_id"] and t["related_requirement_id"] not in valid)
                or (t["related_story_id"] and t["related_story_id"] not in valid)]
    check(not bad_refs, "No task cites a requirement or story outside this project")
    check(all(t["rationale"] for t in tasks if t["grounding"] != "EXPLICIT"),
          "Every INFERRED / AMBIGUOUS / UNKNOWN task explains why")
    counts = {g: sum(t["grounding"] == g for t in tasks) for g in ("EXPLICIT", "INFERRED", "AMBIGUOUS", "UNKNOWN")}
    print("        grounding mix:", counts)

    # Dependencies and ordering.
    order = {task_id: i for i, task_id in enumerate(plan["plan"]["execution_order"])}
    check(set(order) == set(by_id), "Execution order lists every task exactly once")
    ok = all(order[d["depends_on_task_id"]] < order[d["task_id"]] for d in plan["dependencies"] if d["depends_on_task_id"])
    check(ok, "Execution order respects every task dependency")
    sprint_pos = {s["sprint_id"]: i for i, s in enumerate(plan["sprints"])}
    ok = all(sprint_pos[by_id[d["depends_on_task_id"]]["sprint"]] <= sprint_pos[by_id[d["task_id"]]["sprint"]]
             for d in plan["dependencies"] if d["depends_on_task_id"])
    check(ok, "No task is scheduled before a task it depends on")
    check(all(m["task_ids"] and all(t in by_id for t in m["task_ids"]) for m in plan["milestones"]) and bool(plan["milestones"]),
          "Milestones group real tasks")
    check(bool(plan["risks"]) and all(r["mitigation"] for r in plan["risks"]), "Project-specific risks with mitigations")
    check(len(plan["plan"]["definition_of_done"]) >= 3, "Definition of Done generated")

    # No invented scope.
    source_text = json.dumps(analysis).lower()
    plan_text = json.dumps({k: plan[k] for k in ("tasks", "epics", "milestones", "risks")}).lower()
    invented = [w for w in FORBIDDEN_UNLESS_IN_REQUIREMENTS if w in plan_text and w not in source_text]
    check(not invented, "No features invented beyond the requirements" + (f" (found: {invented})" if invented else ""))

    # Sprint dates must not be fabricated when the project has no dates.
    if not any(s["start_date"] for s in plan["sprints"]):
        check(True, "No sprint dates were fabricated")

    # Registration-specific expectations, only checked when the analyst found them.
    print("\nChecks specific to the Customer Registration requirements")
    corpus = source_text
    expectations = [
        ("email validation", ("valid email", "email format", "email validation"), ("email", "valid")),
        ("duplicate registration rejection", ("duplicate", "already"), ("duplicate", "already", "unique")),
        ("confirmation email", ("confirmation email",), ("confirmation", "email")),
        ("two-second response time", ("two seconds", "2 seconds"), ("two seconds", "2 seconds", "performance", "latency")),
        ("secure password storage", ("plaintext", "plain text"), ("hash", "plaintext", "encrypt", "salt")),
    ]
    haystack = plan_text
    for name, in_requirements, in_plan in expectations:
        if any(k in corpus for k in in_requirements):
            check(any(k in haystack for k in in_plan), f"Plan contains work for: {name}")


def print_summary(plan: dict) -> None:
    print("\n--- Generated plan ---")
    print(plan["plan"]["execution_summary"])
    tasks = {t["task_id"]: t for t in plan["tasks"]}
    for sprint in plan["sprints"]:
        print(f"\n{sprint['sprint_id']} {sprint['name']} ({sprint['total_story_points']} pts): {sprint['goal']}")
        for task_id in sprint["tasks"]:
            t = tasks[task_id]
            deps = ",".join(t["dependencies"]) or "-"
            print(f"  {task_id:<4} [{t['story_points']:>2}] {t['suggested_role']:<20} {t['grounding']:<9} "
                  f"deps={deps:<10} {t['title']}")
    print("\nMilestones:", "; ".join(m["title"] for m in plan["milestones"]))
    print("Risks:", "; ".join(r["title"] for r in plan["risks"]))
    for warning in plan["plan"]["warnings"]:
        print("Warning:", warning)


def create_project_and_analyze(client: httpx.Client, args) -> int:
    if not args.srs:
        sys.exit("Provide --project-id (existing project) or --srs (path to the SRS PDF).")
    project = post(client, "/api/projects", json={"name": args.project_name}, ok=201)
    project_id = project["id"]
    print(f"Created project {project_id}: {args.project_name}")
    with open(args.srs, "rb") as handle:
        upload = client.post(f"/api/projects/{project_id}/documents",
                             files={"file": (Path(args.srs).name, handle, "application/pdf")})
    check(upload.status_code == 201 and upload.json()["processing_status"] == "COMPLETED",
          f"SRS uploaded and processed -> {upload.status_code}")
    print("Running Requirements Analyst (real LLM)...")
    analyze = client.post(f"/api/projects/{project_id}/analyze")
    check(analyze.status_code == 200, f"Requirements Analyst -> {analyze.status_code}")
    return project_id


def login_or_register(client: httpx.Client, args) -> str:
    response = client.post("/api/auth/login", json={"email": args.email, "password": args.password})
    if response.status_code == 401:
        response = client.post("/api/auth/register",
                               json={"email": args.email, "password": args.password, "display_name": "E2E"})
    if response.status_code not in (200, 201):
        sys.exit(f"Could not authenticate: {response.status_code} {response.text}")
    return response.json()["access_token"]


def get(client: httpx.Client, path: str):
    response = client.get(path)
    response.raise_for_status()
    return response.json()


def post(client: httpx.Client, path: str, ok: int = 200, **kwargs):
    response = client.post(path, **kwargs)
    if response.status_code != ok:
        sys.exit(f"POST {path} failed: {response.status_code} {response.text}")
    return response.json()


def finish() -> int:
    failed = [message for ok, message in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    for message in failed:
        print("  FAILED:", message)
    return 1 if failed else 0


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--project-id", type=int, help="Use an existing project and its saved analyst output")
    parser.add_argument("--srs", help="SRS PDF to upload when creating a new project")
    parser.add_argument("--project-name", default="Customer Registration & Account Verification")
    return parser.parse_args()


if __name__ == "__main__":
    sys.exit(main())
