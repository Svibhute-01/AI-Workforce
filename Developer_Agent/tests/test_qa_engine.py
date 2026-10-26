import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx
import pytest

from app.qa.engine import MISSING, aggregate, get_path, overall, run_plan, same_value
from app.qa.schemas import Assertion, Expect, HeaderPair, QAPlan, Save, Scenario, Step, Untestable


class Shop(BaseHTTPRequestHandler):
    """A tiny real web app: register, login, a protected page, a leaky endpoint, a redirect."""
    users: dict = {}

    def log_message(self, *args):
        pass

    def _send(self, status, body, content_type="application/json", extra=None):
        data = body.encode() if isinstance(body, str) else json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json(self):
        length = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self):
        if self.path == "/":
            return self._send(200, "<h1>Welcome home</h1>", "text/html")
        if self.path == "/me":
            token = (self.headers.get("Authorization") or "").replace("Bearer ", "")
            email = token.removeprefix("tok-")
            return self._send(200, {"email": email}) if email in self.users else self._send(401, {"detail": "no"})
        if self.path == "/leaky":
            return self._send(200, {"email": "a@b.c", "password": "secret"})
        if self.path == "/redirect":
            return self._send(302, "", "text/plain", {"Location": "http://evil.example/"})
        if self.path == "/big":
            return self._send(200, "x" * 5000, "text/plain")
        self._send(404, {"detail": "not found"})

    def do_POST(self):
        body = self._json()
        if self.path == "/register":
            if body["email"] in self.users:
                return self._send(409, {"detail": "exists"})
            self.users[body["email"]] = body["password"]
            return self._send(201, {"email": body["email"], "id": len(self.users)})
        if self.path == "/login":
            if self.users.get(body.get("email")) == body.get("password"):
                return self._send(200, {"access_token": "tok-" + body["email"], "token_type": "bearer"})
            return self._send(401, {"detail": "bad"})
        self._send(404, {"detail": "not found"})


@pytest.fixture(scope="module")
def base_url():
    server = HTTPServer(("127.0.0.1", 0), Shop)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def expect(status=(200,), equals=(), present=(), absent=(), contains=(), not_contains=()):
    return Expect(status_in=list(status), json_equals=[Assertion(path=p, value=v) for p, v in equals],
                  json_present=list(present), json_absent=list(absent), body_contains=list(contains), body_absent=list(not_contains))


def step(method, path, body="", headers=(), save=(), name="step", **kwargs):
    return Step(name=name, method=method, path=path, json_body=body,
                headers=[HeaderPair(name=n, value=v) for n, v in headers], expect=expect(**kwargs),
                save=[Save(variable=v, path=p) for v, p in save])


def scenario(criterion, *steps, title="scenario"):
    return Scenario(criterion_id=criterion, title=title, steps=list(steps))


def run(base_url, *scenarios):
    return run_plan(base_url, list(scenarios))


# --- helpers --------------------------------------------------------------------------------------

def test_json_paths():
    data = {"a": {"b": [{"c": 5}, {"c": 6}]}, "ok": True}
    assert get_path(data, "$.a.b[1].c") == 6
    assert get_path(data, "$.a.zzz") is MISSING and get_path(data, "$.a.b[9]") is MISSING
    assert get_path(data, "$") == data


@pytest.mark.parametrize("actual, expected, same", [
    (3, "3", True), (3.0, "3", True), (True, "true", True), (None, "null", True), ("x", "x", True),
    ("x", "y", False), (3, "4", False), (False, "true", False),
])
def test_value_comparison(actual, expected, same):
    assert same_value(actual, expected) is same


# --- scenarios against a real server ---------------------------------------------------------------

def test_a_register_login_and_protected_page_flow_passes(base_url):
    result, = run(base_url, scenario(
        "C1",
        step("POST", "/register", '{"email": "qa-{{uniq}}@x.io", "password": "pw"}', status=(201,),
             equals=[("$.email", "qa-{{uniq}}@x.io")], absent=["$.password"], save=[("who", "$.email")]),
        step("POST", "/login", '{"email": "{{who}}", "password": "pw"}', status=(200,), save=[("token", "$.access_token")]),
        step("GET", "/me", headers=[("Authorization", "Bearer {{token}}")], status=(200,), equals=[("$.email", "{{who}}")]),
    ))
    assert result.verdict == "PASS" and [s.passed for s in result.steps] == [True, True, True]


def test_unique_values_differ_between_scenarios(base_url):
    one = scenario("C1", step("POST", "/register", '{"email": "{{uniq}}@x.io", "password": "p"}', status=(201,)))
    two = scenario("C1", step("POST", "/register", '{"email": "{{uniq}}@x.io", "password": "p"}', status=(201,)))
    assert [r.verdict for r in run(base_url, one, two, one)] == ["PASS", "PASS", "PASS"]


def test_a_wrong_status_is_a_defect_with_evidence(base_url):
    result, = run(base_url, scenario("C2", step("GET", "/", status=(201,), name="open home")))
    assert result.verdict == "FAIL"
    assert "expected status [201], got 200" in result.message and "open home" in result.message
    assert result.steps[0].status == 200 and "Welcome" in result.steps[0].excerpt


def test_a_secret_in_the_response_fails_the_criterion(base_url):
    result, = run(base_url, scenario("C3", step("GET", "/leaky", absent=["$.password"])))
    assert result.verdict == "FAIL" and "$.password must not be in the response" in result.message


def test_web_page_text_checks(base_url):
    assert run(base_url, scenario("C4", step("GET", "/", contains=["Welcome"], not_contains=["Error"])))[0].verdict == "PASS"
    failed = run(base_url, scenario("C4", step("GET", "/", contains=["Login"])))[0]
    assert failed.verdict == "FAIL" and "does not contain 'Login'" in failed.message


def test_a_scenario_stops_at_its_first_failing_step(base_url):
    result, = run(base_url, scenario("C5", step("GET", "/nope", status=(200,)), step("GET", "/", status=(200,))))
    assert result.verdict == "FAIL" and len(result.steps) == 1


def test_a_field_the_response_lacks_fails_instead_of_breaking_the_test(base_url):
    result, = run(base_url, scenario("C6", step("GET", "/", save=[("token", "$.access_token")], contains=["Welcome"])))
    assert result.verdict == "FAIL" and "could not read $.access_token" in result.message


def test_redirects_are_not_followed_so_a_test_cannot_leave_the_app(base_url):
    result, = run(base_url, scenario("C7", step("GET", "/redirect", status=(302,))))
    assert result.verdict == "PASS" and result.steps[0].status == 302


def test_long_responses_are_cut_in_the_evidence(base_url):
    result, = run(base_url, scenario("C8", step("GET", "/big", status=(200,))))
    assert len(result.steps[0].excerpt) == 1500


# --- a wrong TEST is not a defect in the app --------------------------------------------------------

@pytest.mark.parametrize("bad_step, message", [
    (step("GET", "/me", headers=[("Authorization", "Bearer {{token}}")]), "variable 'token' is used before"),
    (step("POST", "/login", "{not json}"), "not valid JSON"),
    (step("GET", "http://evil.example/steal"), "must start with a single /"),
    (step("GET", "//evil.example/x"), "must start with a single /"),
    (step("GET", "/", status=()), "status_in is empty"),
    (step("GET", "/", equals=[("name", "x")]), "must start with $"),
])
def test_broken_tests_are_reported_as_spec_errors(base_url, bad_step, message):
    result, = run(base_url, scenario("C9", bad_step))
    assert result.verdict == "ERROR" and result.kind == "spec" and message in result.message


def test_a_scenario_without_steps_is_a_spec_error(base_url):
    assert run(base_url, scenario("C9"))[0].kind == "spec"


def test_an_app_that_does_not_answer_is_a_network_error():
    result, = run_plan("http://127.0.0.1:9", [scenario("C10", step("GET", "/"))])
    assert result.verdict == "ERROR" and result.kind == "network"


# --- verdicts per criterion --------------------------------------------------------------------------

CRITERIA = [{"id": f"C{i}", "text": f"criterion {i}"} for i in range(1, 6)]


def make_results(base_url):
    return run(
        base_url,
        scenario("C1", step("GET", "/", contains=["Welcome"])),
        scenario("c2", step("GET", "/", contains=["Missing text"])),          # ids are matched ignoring case
        scenario("C4", step("GET", "/", status=())),                          # a broken test
    )


def test_every_criterion_gets_a_verdict_with_a_reason(base_url):
    plan = QAPlan(scenarios=[], untestable=[Untestable(criterion_id="C3", reason="email delivery")])
    rows = {row["id"]: row for row in aggregate(CRITERIA, plan, make_results(base_url))}
    assert rows["C1"]["verdict"] == "PASS"
    assert rows["C2"]["verdict"] == "FAIL" and "does not contain 'Missing text'" in rows["C2"]["reason"]
    assert rows["C3"]["verdict"] == "UNVERIFIED" and "email delivery" in rows["C3"]["reason"]
    assert rows["C4"]["verdict"] == "UNVERIFIED" and "could not run" in rows["C4"]["reason"]
    assert rows["C5"]["verdict"] == "UNVERIFIED" and "no test was produced" in rows["C5"]["reason"]
    assert rows["C2"]["scenarios"][0]["steps"][0]["failures"]


def test_the_overall_verdict_and_coverage(base_url):
    plan = QAPlan(scenarios=[], untestable=[])
    summary = overall(aggregate(CRITERIA, plan, make_results(base_url)))
    assert summary["verdict"] == "FAIL" and summary["counts"] == {"PASS": 1, "FAIL": 1, "UNVERIFIED": 3}
    assert summary["total"] == 5 and summary["coverage"] == 40.0


def test_overall_pass_needs_a_verified_criterion_and_no_failures(base_url):
    plan = QAPlan(scenarios=[], untestable=[])
    rows = aggregate(CRITERIA[:2], plan, run(base_url, scenario("C1", step("GET", "/", contains=["Welcome"]))))
    assert overall(rows)["verdict"] == "PASS"
    assert overall(aggregate(CRITERIA[:1], plan, []))["verdict"] == "INCONCLUSIVE"
    assert overall([])["coverage"] == 0.0
