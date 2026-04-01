"""Agents package for web-automation-agent."""

from agents.page_analyzer import PageAnalyzerAgent, PageType
from agents.form_filler import FormFillerAgent
from agents.mcq_solver import MCQSolverAgent
from agents.navigator import NavigatorAgent
from agents.controller import ControllerAgent

__all__ = [
    "ControllerAgent",
    "FormFillerAgent",
    "MCQSolverAgent",
    "NavigatorAgent",
    "PageAnalyzerAgent",
    "PageType",
]
