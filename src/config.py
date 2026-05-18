from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass
class BotConfig:
    token: str
    bothub_api_key: str


@dataclass
class PaymentsConfig:
    provider_token: str
    currency: str

    @property
    def is_configured(self) -> bool:
        return bool(self.provider_token)


@dataclass
class Config:
    bot: BotConfig
    payments: PaymentsConfig
    database_path: str
    initial_free_generations: int


def load_config() -> Config:
    repo_root = Path(__file__).resolve().parent.parent
    default_db = repo_root / "data" / "bot.db"
    payment_currency = os.getenv("PAYMENTS_CURRENCY", "RUB").upper()
    return Config(
        bot=BotConfig(
            token=os.getenv("BOT_TOKEN", ""),
            bothub_api_key=os.getenv("BOTHUB_API_KEY", ""),
        ),
        payments=PaymentsConfig(
            provider_token=os.getenv(
                "YOOKASSA_PROVIDER_TOKEN",
                os.getenv("PAYMENT_PROVIDER_TOKEN", ""),
            ),
            currency=payment_currency,
        ),
        database_path=os.getenv("DATABASE_PATH", str(default_db)),
        initial_free_generations=int(os.getenv("INITIAL_FREE_GENERATIONS", "0")),
    )
