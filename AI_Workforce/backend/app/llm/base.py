from abc import ABC, abstractmethod

from ..schemas import RequirementsAnalysis
from ..schemas_architect import HighLevelDesign, LowLevelDesign
from ..schemas_pm import ProjectPlan


class LLMProvider(ABC):
    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

    @abstractmethod
    def generate_analysis(self, project_name: str, project_description: str, contexts: list[dict]) -> RequirementsAnalysis:
        raise NotImplementedError

    @abstractmethod
    def answer_question(self, question: str, contexts: list[dict]) -> str:
        raise NotImplementedError

    @abstractmethod
    def generate_project_plan(
        self,
        project_name: str,
        project_description: str,
        requirements: dict,
        project_info: dict,
        feedback: list[str] | None = None,
    ) -> ProjectPlan:
        """Create a project plan from validated Requirements Analyst output.

        ``feedback`` lists validation problems from a previous attempt so the
        model can repair its plan.
        """
        raise NotImplementedError

    def generate_hld(
        self,
        project_name: str,
        project_description: str,
        requirements: dict,
        plan: dict,
        preferred_stack: dict,
        feedback: list[str] | None = None,
    ) -> HighLevelDesign:
        """Create the high-level design from validated Requirements Analyst and Project Manager output.

        ``feedback`` lists validation problems from a previous attempt so the model can
        repair its design. Not abstract: providers that cannot design simply do not support it.
        """
        raise NotImplementedError("This provider does not support architecture generation.")

    def generate_lld(
        self,
        project_name: str,
        project_description: str,
        requirements: dict,
        plan: dict,
        hld: dict,
        preferred_stack: dict,
        feedback: list[str] | None = None,
    ) -> LowLevelDesign:
        """Create the low-level design on top of an already validated high-level design."""
        raise NotImplementedError("This provider does not support architecture generation.")
