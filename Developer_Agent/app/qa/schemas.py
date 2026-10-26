"""The QA agent's test plan. Gemini writes tests as DATA (a request and what to expect back);
our own engine runs them. No AI-written code is executed, so a test can be wrong but cannot crash.

Every field is required (an empty string or list means 'unused'), because the model's structured-output
format has no optional fields or free-form dictionaries.
"""

from typing import Literal

from pydantic import BaseModel, Field


class Assertion(BaseModel):
    path: str = Field(description="JSON path of a field in the response, such as $.email or $.items[0].id")
    value: str = Field(description="Expected value as text: strings as they are, numbers like 3, booleans true or false, null as null")


class HeaderPair(BaseModel):
    name: str
    value: str


class Expect(BaseModel):
    status_in: list[int] = Field(description="Acceptable HTTP status codes, for example [201] or [200, 201]. Never empty")
    json_equals: list[Assertion] = Field(description="JSON fields that must equal a value. Empty list when unused")
    json_present: list[str] = Field(description="JSON paths that must exist. Empty list when unused")
    json_absent: list[str] = Field(description="JSON paths that must NOT exist, for example $.password. Empty list when unused")
    body_contains: list[str] = Field(description="Text the response body must contain (for web pages). Empty list when unused")
    body_absent: list[str] = Field(description="Text the response body must NOT contain. Empty list when unused")


class Save(BaseModel):
    variable: str = Field(description="Name to store the value under, used later as {{name}}")
    path: str = Field(description="JSON path of the value to store, such as $.access_token")


class Step(BaseModel):
    name: str = Field(description="What this step does, in a few words")
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    path: str = Field(description="URL path starting with /, for example /api/v1/auth/login. May contain {{variables}}")
    json_body: str = Field(description="Request body as JSON text, or an empty string when there is no body")
    headers: list[HeaderPair] = Field(description="Extra request headers, for example Authorization: Bearer {{token}}. Empty list when unused")
    expect: Expect
    save: list[Save] = Field(description="Values to remember from the response. Empty list when unused")


class Scenario(BaseModel):
    criterion_id: str = Field(description="The id of the acceptance criterion this scenario checks, for example C1")
    title: str
    steps: list[Step] = Field(description="Steps run in order; the scenario stops at the first step that fails")


class Untestable(BaseModel):
    criterion_id: str
    reason: str = Field(description="Why this criterion cannot be checked over HTTP")


class QAPlan(BaseModel):
    scenarios: list[Scenario]
    untestable: list[Untestable] = Field(description="Criteria that cannot be tested over HTTP, each with a reason")
