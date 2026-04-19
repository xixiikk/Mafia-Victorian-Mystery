import re
from llm_players.llm_wrapper import LLMWrapper
from llm_players.logger import Logger
from llm_players.llm_constants import turn_task_into_prompt
from abc import ABC, abstractmethod
ROLE_MAFIA = "mafia"
ROLE_CIVILIAN = "civilian"
ROLE_COMMISSAR = "commissar"


class LLMPlayer(ABC):

    TYPE_NAME = None

    def __init__(self, name, role, llm_config, game_dir, **kwargs):
        self.name = name
        self.role = role
        self.game_dir = game_dir
        self.is_mafia = (role == ROLE_MAFIA)
        self.logger = Logger(name, game_dir)
        self.llm = LLMWrapper(self.logger, **llm_config)
    def get_system_info_message(self):
        return f"""
                Name: {self.name}
                Role: {self.role}
                Keep messages short.
                """

class MafiaPlayer(LLMPlayer):

    TYPE_NAME = ROLE_MAFIA

    def should_generate_message(self, context):
        decision = self.llm.generate(
            prompt="Decide whether to speak",
            system_info=self.get_system_info_message(self)
        )
        return self.interpret_scheduling_decision(decision)

    def generate_message(self, message_history):
        task = "You are mafia. Be short, hide your role, confuse others."
        prompt = turn_task_into_prompt(task, message_history)

        system_info = self.get_system_info_message()

        msg = self.llm.generate(
            prompt,
            system_info=system_info
        )

        return msg.strip()[:120]
    
class CivilianPlayer(LLMPlayer):

    TYPE_NAME = ROLE_CIVILIAN

    def should_generate_message(self, context):
        return True  

    def generate_message(self, message_history):
        task = "You are a civilian. Find mafia and express suspicion."
        prompt = turn_task_into_prompt(task, message_history)

        system_info = self.get_system_info_message()

        msg = self.llm.generate(
            prompt,
            system_info=system_info
        )


        return msg.strip()[:120]
    
class CommissarPlayer(LLMPlayer):

    TYPE_NAME = ROLE_COMMISSAR

    def should_generate_message(self, context):
        return True

    def generate_message(self, message_history):
        task = "You are commissar. Find mafia but do not reveal your role."

        prompt = turn_task_into_prompt(task, message_history)

        system_info = self.get_system_info_message()

        msg = self.llm.generate(
            prompt,
            system_info=system_info
        )

        return msg.strip()[:120]

    def get_system_info_message(self):
        return f"""
Your name is {self.name}.
Your role is {self.role}.

Rules:
- Keep messages short (max 15 words)
- Act like a real human in Mafia game
- Do not reveal hidden role
"""

    def interpret_scheduling_decision(self, decision):
        if decision and "pass" in decision.lower():
            return False
        return True
    def get_vote(self, message_history, candidate_vote_names):
        task = (f"From the following remaining players, which player you want to vote for " \
               f"to eliminate? Base your answer on the conversation as seen in the message " \
               f"history, and especially on what you ({self.name}) said. " \
               f"Reply with only one name from the list, and nothing but that name: "
               f"Players: {', '.join(candidate_vote_names)}")
        prompt = turn_task_into_prompt(task, message_history)
        system_info = self.get_system_info_message()

        vote = self.llm.generate(prompt, system_info)

        return vote
    print("creating player...")

player = MafiaPlayer(
    name="Bot1",
    role="mafia",
    llm_config={},
    game_dir="."
)

print(player.generate_message(["A: hi", "B: suspicious"]))