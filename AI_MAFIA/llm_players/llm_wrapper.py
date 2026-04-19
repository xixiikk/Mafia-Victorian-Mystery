from dotenv import load_dotenv
import os
from openai import OpenAI
load_dotenv()
class LLMWrapper:
    def __init__(self, logger, **config):
        self.logger = logger
        self.client = OpenAI(
            base_url = "http://api.deepseek.com", 
            api_key = os.getenv("API_key")
        )
        self.model = "deepseek-chat"

    def generate(self, prompt, system_info):
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_info},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5
            )

            text = response.choices[0].message.content

            if self.logger:
                self.logger.log(f"LLM: {text}")

            return text.strip()

        except Exception as e:
            if self.logger:
                self.logger.log(f"LLM error: {e}")

            return "error"