import os
import discord
import random
import pydub
import tempfile
from discord.ext import commands
from dotenv import load_dotenv
from discord.sinks import MP3Sink
from oai import save_as_docx, transcribe_audio

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.messages = True
intents.typing = True
intents.message_content = True

bot = commands.Bot(command_prefix='$', intents=intents)
connections = {}


@bot.event
async def on_ready():
    guild_count = 0

    for guild in bot.guilds:
        print(f"- {guild.id} (name: {guild.name})")

        guild_count += 1

    print(f"DnD Bot is in {guild_count} guilds.")

# Commands


@bot.command()
async def roll(ctx, arg=20):
    try:
        converted = int(arg)
        await ctx.send(random.randrange(converted))
    except Exception as e:
        print(e)
        await ctx.send("Please only pass numbers as an argument!")


@bot.command()
async def record(ctx):
    voice = ctx.author.voice

    if not voice:
        await ctx.send("You aren't in a voice channel!")

    # Connect to the voice channel the author is in.
    vc: discord.VoiceClient = await voice.channel.connect()

    # Updateing the chache with the guild and channel.
    connections.update({ctx.guild.id: vc})

    vc.start_recording(
        MP3Sink(),
        once_done,
        ctx.channel,
        sync_start=True,  # WARNING: unstable feature
    )
    await ctx.send("Started recording!")


async def once_done(sink: discord.sinks, channel: discord.TextChannel):
    await channel.send("Processing recordings...")
    transcription = await process_audio_and_transcribe(sink)
    docx_filename = await save_transcription_to_docx(transcription)
    await send_docx_to_channel(channel, docx_filename)


async def process_audio_and_transcribe(sink: discord.sinks):
    mention_strs = []
    audio_segs: list[pydub.AudioSegment] = []
    longest = pydub.AudioSegment.empty()

    for user_id, audio in sink.audio_data.items():
        mention_strs.append(F"<@{user_id}>")
        seg = pydub.AudioSegment.from_file(audio.file, format="mp3")
        if len(seg) > len(longest):
            audio_segs.append(longest)
            longest = seg
        else:
            audio_segs.append(seg)
        audio.file.seek(0)

    for seg in audio_segs:
        longest = longest.overlay(seg)

    with tempfile.NamedTemporaryFile(suffix=".mp3") as temp_file:
        longest.export(temp_file.name, format="mp3")
        transcription = transcribe_audio(temp_file.name)

    return transcription


async def save_transcription_to_docx(transcription):
    docx_filename = 'session_notes.docx'
    save_as_docx({'Transcription': transcription}, docx_filename)
    return docx_filename


async def send_docx_to_channel(channel: discord.TextChannel,
                               docx_filename: str):
    await channel.send(file=discord.File(docx_filename))
    os.remove(docx_filename)


@bot.command()
async def stop(ctx):
    if ctx.guild.id in connections:
        vc = connections[ctx.guild.id]
        vc.stop_recording()
        del connections[ctx.guild.id]
    else:
        await ctx.send("I am currently not recording here.")


@bot.command()
async def leave(ctx):
    vc: discord.VoiceClient = ctx.voice_client

    if not vc:
        return await ctx.send("I'm not in a vc right now")

    await vc.disconnect()

bot.run(DISCORD_TOKEN)
