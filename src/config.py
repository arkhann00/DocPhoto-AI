from dataclasses import dataclass
import os

from dotenv import load_dotenv

load_dotenv()


@dataclass
class BotConfig:
    token: str
    bothub_api_key: str


@dataclass
class Config:
    bot: BotConfig


def load_config() -> Config:
    return Config(
        bot=BotConfig(
            token=os.getenv("BOT_TOKEN", ""),
            bothub_api_key=os.getenv("BOTHUB_API_KEY", ""),
        )
    )
