from __future__ import annotations

import asyncio
from colorama import Fore
import re
import bdb
import time
import logging
import json
from string import Template
from pydantic import Field
from typing import TYPE_CHECKING, List, Tuple
from termcolor import colored

# from multiagents.environments import PipelineEnvironment
from multiagents.message import SolverMessage, Message, CriticMessage
from multiagents.memory import BaseMemory, ChatHistoryMemory
from multiagents.agents import agent_registry
from multiagents.agents.base import BaseAgent
from multiagents.utils.utils import AgentCriticism
from multiagents.tools.api_retrieval import APICaller
from multiagents.reasoning_algorithms import UCT_vote_function, node_to_chain
from multiagents.utils.utils import AgentAction, AgentFinish
from multiagents.reasoning_algorithms import base_env
from prompt_templates.Report_prompts import  ANOMALY_DESC_PROMPT, ANOMALY_TITLE_PROMPT

@agent_registry.register("reporter") # solver is also tool agent by default
class ReporterAgent(BaseAgent):
    class Config:
        arbitrary_types_allowed = True

    verbose: bool = Field(default=False)
    name: str = Field(default="ChiefDBA")
    start_time: str = ""
    max_history: int = 3
    alert_str: str = ""
    alert_dict: dict = {}
    anomaly_desc_prompt: str = ANOMALY_DESC_PROMPT
    anomaly_title_prompt: str = ANOMALY_TITLE_PROMPT
    messages: List[dict] = []

    report: dict = {"title": "", "anomaly date": "", "anomaly description": "", "root cause": "", "diagnosis process": "", "solutions": ""}

    record: dict = {"anomalyAnalysis": {"RoleAssigner":{"messages":[]},"CpuExpert":{"messages":[]},"MemoryExpert":{"messages":[]},"IoExpert":{"messages":[]},"NetworkExpert":{"messages":[]}}, "brainstorming": {"messages":[]}, "report":{}, "title":"alert name", "time":"alert time", "topMetrics": []} # type: bar / line

    def initialize_report(self):
        
        seconds = int(self.start_time)
        start_date = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(seconds))
        self.report["anomaly date"] = start_date
        self.record["time"] = self.start_time

        if self.alert_str == "":
            return

        anomaly_desc_prompt = self.anomaly_desc_prompt.replace("{anomaly_str}", self.alert_str)
        anomaly_desc_message = self.llm._construct_messages(anomaly_desc_prompt)
        
        self.llm.change_messages(self.role_description, anomaly_desc_message)

        anomaly_desc = self.llm.parse()
        anomaly_desc = anomaly_desc['content']
        self.report["anomaly description"] = anomaly_desc

        anomaly_title_prompt = self.anomaly_title_prompt.replace("{anomaly_str}", self.alert_str)
        anomaly_title_message = self.llm._construct_messages(anomaly_title_prompt)
        self.llm.change_messages(self.role_description, anomaly_title_message)
        anomaly_title = self.llm.parse()
        anomaly_title = anomaly_title['content']
        self.report["title"] = anomaly_title.replace('\\"','')
        self.report["title"] = anomaly_title.replace('"','')
        self.record["title"] = anomaly_title.replace('\\"','')
        self.record["title"] = anomaly_title.replace('"','')

        self.record["severity"] = []        
        self.record["status"] = []
        alert_names = []
        for alert in self.alert_dict:

            if isinstance(alert, dict):
                alert_names.append({"alert_name": alert['alert_name'],
                                "alert_status": alert['alert_status'],
                                "alert_level": alert['alert_level']})

            # self.record["severity"].append(alert['alert_level'])
            # self.record["status"].append(alert['alert_status'])

            # if isinstance(alert, dict) and  'alert_name' in alert:
            #     alert_names.append(alert['alert_name'])

        self.report["alerts"] = alert_names
        self.record["alerts"] = alert_names

    def update_diagnosis(self):
        prompt = "You are writing a report. Please summarize the refined anomaly diagnosis based on the above review adice. The anomaly diagnosis is as follows:\n" + self.report["root cause"] + "\n ===== \n Note 1. the output should be in markdown format.\n2. do not any additional content like 'Sure' and 'I will refine the anomaly diagnosis description based on the above advice.'\n"

        prompt_message = {"role": "user", "content": prompt, "time": time.strftime("%H:%M:%S", time.localtime())}

        self.messages.append(prompt_message)

        self.llm.change_messages(self.role_description, self.messages)
        new_message = self.llm.parse()
        
        if isinstance(new_message, dict):
            self.report["root cause"] = new_message["content"]
        else:
            self.report["root cause"] = new_message.content


    def update_solutions(self):
        prompt = "You are writing a report. Please summarize the refined solutions based on the above review adice. The solutions are as follows:\n" + self.report["solutions"] + "\n ===== \n Note 1. the output should be in markdown format.\n2. do not any additional content like 'Sure' and 'I will refine the solutions based on the above advice.'\n"

        prompt_message = {"role": "user", "content": prompt, "time": time.strftime("%H:%M:%S", time.localtime())}

        self.messages.append(prompt_message)

        self.llm.change_messages(self.role_description, self.messages)
        new_message = self.llm.parse()

        if isinstance(new_message, dict):
            self.report["solutions"] = new_message["content"]
        else:
            self.report["solutions"] = new_message.content


    async def step(
        self, former_solution: str, advice: str, task_description: str = "", **kwargs
    ):
        pass

    async def astep(self, env_description: str = "") -> SolverMessage:
        """Asynchronous version of step"""
        pass

    def _fill_prompt_template(
        self, env_description: str = "", tool_observation: List[str] = []):
        pass

    
    def add_message_to_memory(self, messages: List[Message]) -> None:
        self.memory.add_message(messages)

    def reset(self) -> None:
        """Reset the agent"""
        self.memory.reset()
        # TODO: reset receiver