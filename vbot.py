from discord.ext import tasks
import discord
import asyncio
from discord.channel import VoiceChannel
from discord import FFmpegPCMAudio
import requests # APIを使う
import json # APIで取得するJSONデータを処理する
import pyaudio
from io import BytesIO

import openai
import speech_recognition as sr

import functools
import typing

from concurrent.futures import ProcessPoolExecutor

openai.api_key = "TOKEN"

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
voiceChannel: VoiceChannel


@client.event
async def on_ready():
    print(f'{client.user} がログインしました')
    global mess


def to_thread(func: typing.Callable) -> typing.Coroutine:
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        wrapped = functools.partial(func, *args, **kwargs)
        return await loop.run_in_executor(None, wrapper)
    return wrapper


def input_voice():
        r = sr.Recognizer()
        with sr.Microphone(sample_rate=16_000) as source:
            print("input start")
            audio = r.listen(source)
            print("input end")
            return audio


async def listen_async(self, source):
    import threading
    loop = asyncio.get_event_loop()
    result_future = asyncio.Future()
    def threaded_listen():
        with source as s:
            try:
                audio = self.listen(s, phrase_time_limit=5)
                loop.call_soon_threadsafe(result_future.set_result, audio)
            except Exception as e:
                loop.call_soon_threadsafe(result_future.set_exception, e)
                return "none"
    listener_thread = threading.Thread(target=threaded_listen)
    listener_thread.daemon = True
    listener_thread.start()
    return await result_future

#@to_thread
@tasks.loop(seconds=3)
async def background_task(message):
    r = sr.Recognizer()
    m = sr.Microphone()
    with sr.Microphone(sample_rate=16_000) as source:
        print("input start")
        audio = await listen_async(r, m);
        print("input end")

    audio_data = BytesIO(audio.get_wav_data())
    audio_data.name = "tmp.wav"
    transcript = openai.Audio.transcribe("whisper-1", audio_data, language='ja')
    text = transcript["text"]
    if text != 'ご視聴ありがとうございました':
        print(text)
        res1 = requests.post('http://127.0.0.1:50021/audio_query',params = {'text': text, 'speaker': 8})
        res2 = requests.post('http://127.0.0.1:50021/synthesis',params = {'speaker': 8},data=json.dumps(res1.json()))
        with open('vox_tmp.wav', mode='wb') as f:
            f.write(res2.content)

        while message.guild.voice_client.is_playing():
            await asyncio.sleep(0.3)
        message.guild.voice_client.play(discord.FFmpegPCMAudio("vox_tmp.wav"))


@client.event
async def on_message(message):
    if message.author.bot:
        return
    print(message.content)
    if message.content == "!join":
        if message.author.voice is None:
            await message.channel.send("あなたはボイスチャンネルに接続していません。")
            await background_task.cancel();
            return
        await message.author.voice.channel.connect()

        await message.channel.send('接続しました。')
        await message.guild.voice_client.move_to(message.author.voice.channel)
        await message.reply('Joined the voice channel!')
        global mess
        mess = message
        background_task.start(message);


    elif message.content == "!exit":
        if message.guild.voice_client is None:
            await message.channel.send("接続していません。")
            return

        await message.guild.voice_client.disconnect()

        await message.channel.send("切断しました。")


    elif message.content == '!exit' and message.guild.voice_client:
        await message.guild.voice_client.disconnect()
        await message.reply('Left the voice channel!')


        await asyncio.sleep(60)
        print('Background task running...')

client.run('DISCORD_TOKEN')#, log_handler=None)
