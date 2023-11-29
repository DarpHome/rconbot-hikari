import asyncio
import io
import traceback
from typing import cast
import hikari
import lightbulb

from ..bot import Bot

plugin = lightbulb.Plugin("base")
from .. import rcon


@plugin.command
@lightbulb.option(
    "port", "RCON server port", type=int, min_value=0, max_value=65535, required=True
)
@lightbulb.command("rcon", "Connect RCON")
@lightbulb.implements(lightbulb.SlashCommand)
async def connect(ctx: lightbulb.SlashContext) -> None:
    bot = cast(Bot, ctx.bot)
    if ctx.author.id in bot.rcons:
        await ctx.respond(
            "You're already connected to RCON. Disconnect from it to change connection.",
            flags=hikari.MessageFlag.EPHEMERAL,
        )
        return
    await ctx.respond_with_modal(
        "Enter credentials",
        f"credentials:{ctx.options.port}",
        components=[
            hikari.impl.ModalActionRowBuilder(
                components=[
                    hikari.impl.TextInputBuilder(
                        custom_id="host",
                        label="Host",
                        style=hikari.TextInputStyle.SHORT,
                        required=True,
                        min_length=2,
                        max_length=64,
                    ),
                ]
            ),
            hikari.impl.ModalActionRowBuilder(
                components=[
                    hikari.impl.TextInputBuilder(
                        custom_id="password",
                        label="Password",
                        style=hikari.TextInputStyle.SHORT,
                        required=True,
                        min_length=1,
                    ),
                ]
            ),
        ],
    )
    await asyncio.sleep(60.0)
    del bot.rcons[ctx.author.id]


@plugin.listener(hikari.events.InteractionCreateEvent)
async def on_modal(event: hikari.events.InteractionCreateEvent) -> None:
    partial = event.interaction
    if partial.type != hikari.InteractionType.MODAL_SUBMIT:
        return
    inter = cast(hikari.ModalInteraction, partial)
    parts = inter.custom_id.split(":", 2)
    if parts[0] != "credentials":
        return
    bot = cast(Bot, event.app)
    if inter.user.id in bot.rcons:
        await inter.create_initial_response(
            hikari.ResponseType.MESSAGE_CREATE,
            "You're already connected to RCON. Disconnect from it to change connection.",
            flags=hikari.MessageFlag.EPHEMERAL,
        )
        return
    port = int(parts[1])
    host = (
        list(filter(lambda r: r.components[0].custom_id == "host", inter.components))[0]
        .components[0]
        .value
    )
    password = (
        list(
            filter(lambda r: r.components[0].custom_id == "password", inter.components)
        )[0]
        .components[0]
        .value
    )
    client = rcon.RCONClient(host, port)
    await inter.create_initial_response(hikari.ResponseType.DEFERRED_MESSAGE_CREATE)
    try:
        await client.open()
    except Exception as exc:
        traceback.print_exception(exc)
        await inter.edit_initial_response(f"Error when connecting: {exc.args}")
        return
    try:
        await client.login(password)
    except ValueError as exc:
        traceback.print_exception(exc)
        await inter.edit_initial_response("Incorrect password")
        await client.close()
        return
    bot.rcons[inter.user.id] = client
    message = await inter.edit_initial_response("Connected. Type commands.")
    while True:
        try:
            m = await bot.wait_for(
                hikari.DMMessageCreateEvent,
                timeout=300.0,
                predicate=lambda event: event.author_id == inter.user.id,
            )
        except asyncio.TimeoutError:
            break
        response = await client.execute(cast(str, m.content))
        if len(response) == 0:
            await m.message.add_reaction("\N{WASTEBASKET}")
        elif len(response) > 2000:
            await m.message.respond(
                "Too large response: sharing file",
                attachment=hikari.Bytes(response, "response.txt"),
            )
        else:
            await m.message.respond(response.replace(b"\xc2\xa7", b"").decode("utf_8"))
    await inter.edit_initial_response("Terminating connection...")
    await client.close()
    del bot.rcons[inter.user.id]


@plugin.command
@lightbulb.command("disconnect", "Disconnect from RCON")
@lightbulb.implements(lightbulb.SlashCommand)
async def disconnect(ctx: lightbulb.SlashContext) -> None:

    await ctx.respond("Disconnected.")

def load(bot: Bot) -> None:
    bot.add_plugin(plugin)


def unload(bot: Bot) -> None:
    bot.remove_plugin(plugin)
