import os
import re
from collections import deque

import openai
from Bard import Chatbot as Bard
from EdgeGPT import Chatbot as Bing
from EdgeGPT import ConversationStyle
from hugchat import hugchat

MODELS = ["bard", "bing", "gpt", "hugchat", "llama"]


class ChatHistory:
    def __init__(self, msg_limit):
        self.stack = deque(maxlen=msg_limit)

    def append(self, msg):
        return self.stack.append(msg)

    def get_as_list(self):
        return list(self.stack)


class ChatModel:
    def __init__(self, model):
        assert (
            model in MODELS
        ), f"value attribute to {__class__.__name__} must be one of {MODELS}"
        self.model = model
        self.trigger = f"!{model}"
        self.api = self.get_api()

    def get_api(self):
        if self.model == "bing":
            return BingAPI(
                cookie_path="./config/bing.json",
                conversation_style=ConversationStyle.balanced,
            )

        if self.model == "bard":
            token = os.getenv("BARD_TOKEN")
            return BardAPI(token)

        if self.model == "gpt":
            openai_api_key = os.getenv("OPENAI_API_KEY")
            openai_api_base = (
                os.getenv("OPENAI_API_BASE") or "https://api.openai.com/v1"
            )
            return OpenAIAPI(api_key=openai_api_key, api_base=openai_api_base)

        if self.model == "hugchat":
            return HugchatAPI(cookie_path="./config/hugchat.json")

        if self.model == "llama":
            llama_api_key = "this_can_be_anything"
            llama_api_base = os.getenv("LLAMA_API_BASE")
            return OpenAIAPI(api_key=llama_api_key, api_base=llama_api_base)


class BardAPI:
    def __init__(self, token):
        self.chat = Bard(token)

    async def send(self, text):
        return self.chat.ask(text)


class BingAPI:
    def __init__(self, cookie_path, conversation_style):
        self.conversation_style = conversation_style
        self.chat = Bing(cookie_path=cookie_path)

    def _cleanup_footnote_marks(self, response):
        return re.sub(r"\[\^(\d+)\^\]", r"[\1]", response)

    def _parse_sources(self, sources_raw):
        name = "providerDisplayName"
        url = "seeMoreUrl"

        sources = ""
        for i, source in enumerate(sources_raw, start=1):
            if name in source.keys() and url in source.keys():
                sources += f"[{i}]: {source[name]}: {source[url]}\n"
            else:
                continue

        return sources

    async def send(self, text):
        data = await self.chat.ask(prompt=text)
        sources_raw = data["item"]["messages"][1]["sourceAttributions"]
        if sources_raw:
            sources = self._parse_sources(sources_raw)
        else:
            sources = ""

        response_raw = data["item"]["messages"][1]["text"]
        response = self._cleanup_footnote_marks(response_raw)

        if sources:
            return f"{response}\n\n{sources}"
        else:
            return response


class HugchatAPI:
    def __init__(self, cookie_path):
        self.chat = hugchat.ChatBot(cookie_path=cookie_path)

    async def send(self, text):
        return self.chat.chat(text)


class OpenAIAPI:
    def __init__(
        self, api_key, api_base, model="gpt-3.5-turbo", max_history=5, max_tokens=1024
    ):
        self.model = model
        self.history = ChatHistory(max_history)
        self.max_tokens = max_tokens
		self.api_key = api_key
		self.api_base = api_base

    async def send(self, text):
        openai.api_key = self.api_key
        openai.api_base = self.api_base

        new_message = {"role": "user", "content": text}
        self.history.append(new_message)
        messages = self.history.get_as_list()

        response = openai.ChatCompletion.create(
            model=self.model, messages=messages, max_tokens=self.max_tokens
        )

        self.history.append(response.choices[0].message)
        response = response.choices[0].message.content
        return response.strip()
