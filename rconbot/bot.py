import lightbulb
from . import rcon


class Bot(lightbulb.BotApp):
    rcons: dict[int, rcon.RCONClient | None]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.rcons = {}
