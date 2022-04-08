import aiohttp
import argparse
import json
import logging
import os

import discord
from discord.ext.commands import Bot

log = logging.getLogger('discord')
log.setLevel(logging.INFO)

LIANTICHESS = os.getenv("LIANTICHESS", "http://127.0.0.1:8080")

TOKEN = os.getenv('DISCORD_TOKEN')
SERVER_ID = 920263455779454997
LIANTICHESS_LOBBY_CHANNEL_ID = 923820641386369084
GAME_SEEK_CHANNEL_ID = 933405389133873173
TOURNAMENT_CHANNEL_ID = 922504976775938088
ANNOUNCEMENT_CHANNEL_ID = 920969508389257226

ROLES = {
    "tournament": 964067396249866240,
}

intents = discord.Intents(messages=True, guilds=True)


class MyBot(Bot):

    async def on_message(self, msg):
        log.debug("---on_message() %s", msg)
        if msg.author.id == self.user.id or msg.channel.id != LIANTICHESS_LOBBY_CHANNEL_ID:
            log.debug("---self.user msg OR other channel.id -> return")
            return

        if self.lobby_ws is None:
            log.debug("---self.lobby_ws is None -> return")
            return
        log.debug("+++ msg is OK -> send_json()")
        await self.lobby_ws.send_json({"type": "lobbychat", "user": "", "message": "%s: %s" % (msg.author.name, msg.content)})


bot = MyBot(command_prefix="!", intents=intents)


def get_role_mentions(bot, message):
    guild = bot.get_guild(SERVER_ID)
    tournament_role = guild.get_role(ROLES["tournament"])
    log.debug("guild, role, intent are: %s %s %s", guild, tournament_role, tournament_role.mention)
    return "%s" % (tournament_role.mention)

async def lobby_task(bot):
    await bot.wait_until_ready()

    # Get the liantichess-lobby channel
    liantichess_lobby_channel = bot.get_channel(LIANTICHESS_LOBBY_CHANNEL_ID)
    log.debug("liantichess_lobby_channel is: %s", liantichess_lobby_channel)

    game_seek_channel = bot.get_channel(GAME_SEEK_CHANNEL_ID)
    log.debug("game_seek_channel is: %s", game_seek_channel)

    tournament_channel = bot.get_channel(TOURNAMENT_CHANNEL_ID)
    log.debug("tournament_channel is: %s", tournament_channel)

    announcement_channel = bot.get_channel(ANNOUNCEMENT_CHANNEL_ID)
    log.debug("announcement_channel is: %s", announcement_channel)

    while True:
        log.debug("+++ Creating new aiohttp.ClientSession()")
        session = aiohttp.ClientSession()

        async with session.ws_connect(LIANTICHESS + '/wsl') as ws:
            bot.lobby_ws = ws
            await ws.send_json({"type": "lobby_user_connected", "username": "Discord-Relay"})
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    # print("msg.data", msg.data)
                    try:
                        if msg.data == 'close':
                            log.debug("!!! Lobby ws got 'close' msg")
                            await ws.close()
                            break
                        else:
                            data = json.loads(msg.data)
                            if data['type'] == 'ping':
                                await ws.send_json({"type": "pong"})
                            elif data['type'] == 'lobbychat' and data['user'] and data['user'] != "Discord-Relay":
                                log.debug("+++ lobbychat msg: %s %s", data['user'], data["message"])
                                await liantichess_lobby_channel.send("**%s**: %s" % (data['user'], data['message']))
                            elif data['type'] == 'create_seek':
                                log.debug("+++ create_seek msg: %s", data["message"])
                                await game_seek_channel.send("%s" % data['message'])
                            elif data['type'] == 'create_tournament':
                                log.debug("+++ create_tournament msg: %s", data["message"])
                                await tournament_channel.send("%s" % data['message'])
                            elif data['type'] == 'notify_tournament':
                                log.debug("+++ notify_tournament msg: %s", data["message"])
                                await announcement_channel.send("%s %s" % (get_role_mentions(bot, data['message']), data['message']))
                    except Exception:
                        logging.exception("baj van")
                elif msg.type == aiohttp.WSMsgType.CLOSE:
                    log.debug("!!! Lobby ws connection closed with aiohttp.WSMsgType.CLOSE")
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    log.debug("!!! Lobby ws connection closed with exception %s", ws.exception())
                else:
                    log.debug("!!! Lobby ws other msg.type %s %s", msg.type, msg)

        bot.lobby_ws = None
        await session.close()


background_task = bot.loop.create_task(lobby_task(bot))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Liantichess discord bot')
    parser.add_argument('-v', action='store_true', help='Verbose output. Changes log level from INFO to DEBUG.')
    parser.add_argument('-w', action='store_true', help='Less verbose output. Changes log level from INFO to WARNING.')
    args = parser.parse_args()

    logging.basicConfig()
    logging.getLogger("discord").setLevel(level=logging.DEBUG if args.v else logging.WARNING if args.w else logging.INFO)

    bot.run(TOKEN)