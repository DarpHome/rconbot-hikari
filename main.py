import asyncio

import dotenv

dotenv.load_dotenv()

import os
import hikari
import lightbulb

from rconbot.bot import Bot


loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

token = os.getenv("DISCORD_BOT_TOKEN")
if not token:
    raise ValueError("token required")

bot = Bot(
    token=token,
    intents=hikari.Intents.GUILD_MESSAGES
    | hikari.Intents.MESSAGE_CONTENT
    | hikari.Intents.DM_MESSAGES,
)


async def main() -> None:
    bot.load_extensions_from("rconbot/ext")
    await bot.start(
        activity=hikari.Activity(name="minecraft", type=hikari.ActivityType.PLAYING)
    )
    # await bot.purge_application_commands(global_commands=True)
    # await bot.sync_application_commands()
    await bot.join()


loop.run_until_complete(main())
