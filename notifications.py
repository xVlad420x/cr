from asyncio import tasks
print("test")

import datetime
import pandas as pd
import sys
import discord
from discord.ext import commands, tasks
from discord.ext.commands import bot
disc_bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())
#disc_bot.run("OTIyNTk1MDM2MzM0NTI2NTA0.GXSkB2.FM9MYhoyN4HZcamYD40ohxduLPQAO4-f6lL54M")

def timestamp():
    return datetime.datetime.now().timestamp()

@disc_bot.event
async def on_ready():
    print("Bot online")
    checkpace.start()
    ratecheck.start()

@disc_bot.command()
async def hello(ctx):
    username = ctx.message.author.name
    await ctx.send("Hello " + username)

# @tasks.loop(seconds=1)
# async def sendmessage():
#      channel = disc_bot.get_channel(922764603031707678)
#      await channel.send("hello4")

@tasks.loop(seconds=300)
async def checkpace():
     channel = disc_bot.get_channel(922764627115393025)
     codes_log = pd.read_csv(sys.argv[1])
     last_rows = codes_log.tail(1)
     last_code = str(last_rows["Code_Number"].to_string(index = False))

     five_mins_ago = timestamp() - 300
     fifteen_mins_ago = timestamp() - 900
     last_5_df = codes_log[codes_log["Timestamp"] >= five_mins_ago]
     last_15_df = codes_log[codes_log["Timestamp"] >= fifteen_mins_ago ]
     quantity_5 = last_5_df.shape[0]
     quantity_15 = last_15_df.shape[0]
     minute_rate = quantity_5/5.0
     minute_rate2 = quantity_15/15.0
     await channel.send("Number of last code punched: " + str(last_code))
     await channel.send("Codes Per Min (from last 5 min): " + str(minute_rate))
     await channel.send("Codes Per Min (from last 15 min): " + str(minute_rate2))


@tasks.loop(seconds=15)
async def ratecheck():
    channel = disc_bot.get_channel(1262991796875821077)
    codes_log = pd.read_csv(sys.argv[1])
    one_mins_ago = timestamp() - 60
    last_1_df = codes_log[codes_log["Timestamp"] >= one_mins_ago]
    minute_rate = last_1_df.shape[0] /1.0
    if codes_log.shape[0] > 10 and minute_rate < 0.1:
        await channel.send("BOT STOPPED!: last code:" + str(codes_log.iloc[-6]["Code_Number"]))

print("here")
def runbot():
    disc_bot.run("OTIyNTk1MDM2MzM0NTI2NTA0.GXSkB2.FM9MYhoyN4HZcamYD40ohxduLPQAO4-f6lL54M")
print("A")

runbot()






