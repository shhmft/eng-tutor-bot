import logging
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_API_BASEURL
import json

# Настраиваем логгер
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FuncGPT:

    def __init__(self, system, model="gpt-4o-mini", oai=None):
        """
        Simple GPT client.

        Args:
            system: system prompt
            model: "gpt-3.5-turbo-0613", "gpt-3.5-turbo"  gpt-3.5-turbo-instruct
            oai: OpenAI instance
        """

        self.model = model
        self.context = [
            {"role": "system", "content": system}
        ]

        if oai is None:
            self.oai = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_API_BASEURL)
        else:
            self.oai = oai

        self.funcs_desc = []
        self.funcs = {}

    def chat(self, message):
        self.context.append({"role": "user", "content": message})
        try:
            resp = self.oai.chat.completions.create(
                messages=self.context,
                model=self.model,
                tools=self.funcs_desc,
                tool_choice="auto"
            )
            logger.info(f"API response: {resp}")
        except Exception as e:
            logger.error(f"API call failed: {e}", exc_info=True)
            raise

        if not resp.choices or not resp.choices[0].message.content:
            logger.error("Received an empty or invalid response from the API")
            self.context.append({"role": "user", "content": 'Я ничего не получил, скажи ученику, что настройки сохранены'})
            try:
                resp = self.oai.chat.completions.create(
                    messages=self.context,
                    model=self.model,
                    tools=self.funcs_desc,
                    tool_choice="auto"
                )
                logger.info(f"Retry response: {resp}")
                if not resp.choices or not resp.choices[0].message.content:
                    raise ValueError("API response is still empty or invalid")
            except Exception as e:
                logger.error(f"API call failed again: {e}")

        response_content = resp.choices[0].message.content

        if resp.choices[0].message.tool_calls:
            func_name = resp.choices[0].message.tool_calls[0].function.name
            if func_name not in self.funcs:
                raise Exception(f"Unknown function: {func_name}")

            args = json.loads(resp.choices[0].message.tool_calls[0].function.arguments)
            func = self.funcs[func_name]
            func_result = func(args)

            self.context.append({"role": "function", "name": func_name, "content": func_result})

            try:
                follow_up = self.oai.chat.completions.create(
                    messages=self.context,
                    model=self.model,
                    tools=self.funcs_desc,
                    tool_choice="auto"
                )
                logger.info(f"Follow-up response: {follow_up}")
                if not follow_up.choices or not follow_up.choices[0].message.content:
                    raise ValueError("Follow-up API response is empty or invalid")
            except Exception as e:
                logger.error(f"Follow-up API call failed: {e}")

            final_output = follow_up.choices[0].message.content
            self.context.append({"role": "assistant", "content": final_output})

            return final_output

        self.context.append({"role": "assistant", "content": resp.choices[0].message.content})

        return resp.choices[0].message.content

    # вывести контекст для отладки без system, в виде диалога
    def debug(self):
        return "\n".join(
            f"[{msg['role']}]" + msg["content"]
            for msg in self.context[1:]
        )

    def add_func(self, descr, func):
        logger.info("!!!add_func!!!")
        """
        Add function to the list of functions.

        Args:
            descr: function description
            func: function

        descr example:
            {
               "type": "function",
               "function": {
                  "name": "send_task_to_assistant",
                  "description": "Send task to assistant",
                  "parameters": {
                     "type": "object",
                     "properties": {
                           "assistant_name": {
                              "type": "string",
                              "description": "Assistant name",
                           },
                           "task": {
                              "type": "string",
                              "description": "Task description in English",
                           },
                           "role": {
                              "type": "string",
                              "description": "Role text",
                           },
                     },
                     "required": ["assistant_name", "task", "role"],
                  }
               }
            }        
        """

        self.funcs_desc.append(descr)

        if not callable(func):
            raise TypeError(f"Function {func} is not callable")

        self.funcs[descr['function']['name']] = func




