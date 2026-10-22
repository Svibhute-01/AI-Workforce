"""LangGraph orchestration for the AI Workforce agent pipeline.

Modules
-------
state       shared ``WorkflowState`` and the error/status vocabulary (no DB imports)
validators  pure validation gates that inspect the shared state
graph       generic builder: turns an ordered list of ``Stage`` objects into a LangGraph
stages      the stages that exist today (Requirements Analyst, Project Manager)
service     ``WorkflowService``: runs the graph and reports failures

Adding a future agent (Developer, QA) means writing its node and
validation gate and appending one ``Stage`` to ``default_stages``; the builder, the
state and the existing stages do not change.
"""
