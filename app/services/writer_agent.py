import json
import logging
from typing import TypedDict, List
from app.services.client import client
from app.prompts.agent import ARCHITECT_PROMPT, AUDITOR_PROMPT, SURGEON_PROMPT
from langgraph.graph import StateGraph, END

logger = logging.getLogger(__name__)

class AgentState(TypedDict):
    topic: str
    content: dict
    critique: str
    iterations: int

class WriterAgent:
    def __init__(self):
        workflow = StateGraph(AgentState)

        workflow.add_node("architect", self.architect_node)
        workflow.add_node("auditor", self.auditor_node)
        workflow.add_node("surgeon", self.surgeon_node)

        workflow.set_entry_point("architect")
        workflow.add_edge("architect", "auditor")

        workflow.add_conditional_edges("auditor", self.decide_to_finish, {"refine": "surgeon", "end": END})
        workflow.add_edge("surgeon", "auditor")

        self.app = workflow.compile()

    def architect_node(self, state: AgentState):
        logger.info("Drafting script: %s", state['topic'][:50])
        response = client.chat.completions.create(
            model = 'llama-3.3-70b-versatile',
            messages = [
                {"role": "system", "content": ARCHITECT_PROMPT},
                {"role": "user", "content": state['topic']}
            ],
            response_format = {"type": "json_object"}
        )
        return {
            "content": json.loads(response.choices[0].message.content),
            "iterations": state.get("iterations", 0) + 1
        }
    
    def auditor_node(self, state: AgentState):
        logger.info("Auditing script (attempt %d)", state['iterations'])
        script = state['content']['script']

        response = client.chat.completions.create(
            model = "llama-3.1-8b-instant",
            messages = [
                {"role": "system", "content": AUDITOR_PROMPT},
                {"role": "user", "content": script}
            ]
        )
        return {
            "critique": response.choices[0].message.content,
        }
    
    def surgeon_node(self, state: AgentState):
        logger.info("Fixing script violations")
        instruction = f"VIOLATION: {state['critique']}\nCURRENT SCRIPT: {state['content']['script']}"

        response = client.chat.completions.create(
            model = "llama-3.3-70b-versatile",
            messages = [
                {"role": "system", "content": SURGEON_PROMPT},
                {"role": "user", "content": instruction}
            ],
            response_format = {"type": "json_object"}
        )
        patched = json.loads(response.choices[0].message.content)
        merged = {**state["content"], **patched}
        return {
            "content": merged,
            "iterations": state['iterations'] + 1
        }
    
    def decide_to_finish(self, state: AgentState):
        if "PASS" in state['critique'].upper() or state['iterations'] > 3:
            logger.info("Script approved | iterations: %d", state['iterations'])
            return "end"
        logger.info("Refining script...")
        return "refine"
    
    async def run(self, topic: str):
        initial_state = {"topic": topic, "iterations": 0}
        result = await self.app.ainvoke(initial_state)
        return result['content']