import os
# from dotenv import load_dotenv
import openai
import json
import asyncio
import openai_async
import discord
from discord.ext import commands, tasks
import re

user_file = "users.json"

prompt = "During this conversationg act as if you are the bro-bot discord bot for THE NATION discord channel. You act like a frat boy. You like to crack random jokes that are sometimes about the discord members. You are not afraid of being edgy or huring people's feelings. You are kind of mean. Be as condescending and possible. You know everything about video games and think you are better than everyone else at them."

api_key = os.getenv("API_KEY")
model_id = os.getenv("MODEL")
bot_token = os.getenv("BOT_TOKEN")
channel_id = int(os.getenv("CHANNEL_ID"))
voice_channel_id = int(os.getenv("VOICE_CHANNEL_ID"))
fact_votes_needed = int(os.getenv("FACT_VOTES_NEEDED"))
conversation = []

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='%', intents=intents)

class User:
    def __init__(self, name: str, nicknames: str, facts: list, discord_id):
        self.name = name
        self.nicknames = nicknames
        self.facts = facts
        self.discord_id = discord_id
        self.discord_info = {}
    
    def add_fact(self, fact: str):
        self.facts.append(fact)
        self.update_json()
    
    def fact_exists(self, fact: str) -> bool:
        return fact in self.facts

    def update_json(self):
        with open(user_file, "r+") as f:
            data = json.load(f)
            for user in data["users"]:
                if user["discord_id"] == self.discord_id:
                    user["facts"] = self.facts
            f.seek(0)
            json.dump(data, f, indent=4)
            f.truncate()

    def add_discord_info(self, discord_info):
        self.discord_info = discord_info

def load_users_from_file() -> list:
    with open(user_file, "r") as f:
        data = json.load(f)
        return [User(user["name"], user["nicknames"], user["facts"], user["discord_id"]) for user in data["users"]]

def get_user_by_id(discord_id: int) -> User:
    for user in users:
        if user.discord_id == discord_id:
            return user
    return None

def generate_person_prompt(person: User) -> str:
    prompt = f"{person.name},"
    prompt == f"their discord id is ({person.discord_id}),"
    if person.nicknames:
        prompt += f" also known as the following nicknames [{', '.join(person.nicknames)}]."
    if person.facts:
        prompt += f" Here are some facts about {person.name} [{', '.join(person.facts)}]."
    return prompt

def create_initial_prompt(prompt: str, users: list) -> str:
    person_prompts = []
    person_prompts.append("Below are some of the people you are bros with in this discord:\r")
    for user in users:
        person_prompts.append(generate_person_prompt(user))
        person_prompts.append("\r\r")

    initial_prompt = f"[PROMP]\r{prompt}\r{' '.join(person_prompts)}\rUsers with post messages like this... USER: MESSAGE.\r Do not add a prefix to your messages. respond with the only word OK to this promp nothing else. Everything after END PROMPT should be responded to as bro-bot. [END PROMPT]"
    return initial_prompt

async def gpt_conversation(conversation):
    try:
        response = await openai_async.chat_complete(
            api_key,
            timeout=20,
            payload= {
                'model': "gpt-3.5-turbo",
                'messages': conversation
            }
        )
        response = response.json()
        api_usage = response['usage']
        print('Total token consumed: {0}'.format(api_usage['total_tokens']))
        # stop means complete
        print(response['choices'][0]['finish_reason'])
        print(response['choices'][0]['index'])
        conversation.append({'role': response['choices'][0]['message']["role"], 'content': response['choices'][0]['message']["content"]})
        return conversation
    except Exception as e:
        print(e)
        raise(e)


# @bot.command()
# async def teetimerequest(ctx):
    


@bot.command()
async def fact(ctx, discord_id: int, fact: str):
    try:
        target_user = get_user_by_id(discord_id)
        if target_user is None:
            await ctx.send("User not found.")
            return
        # target_user.add_fact(fact)
        channel = await bot.fetch_channel(channel_id)
        await ctx.send(f"The following fact has been suggested for {target_user.name} [{discord_id}]\r\r{fact}\r\rReact with :white_check_mark: to accept or :x: to reject.")
        async for msg in ctx.channel.history(limit=1):
            message = msg
        await message.add_reaction("✅")
        await message.add_reaction("❌")
    except Exception as e:
        print(e)
        raise(e)

@bot.event
async def on_reaction_add(reaction, user):
    try:
        if user == bot.user:
            return
        message = reaction.message
        if 'The following fact has been suggested for' in message.content:
            if message.channel.id != channel_id:
                return
            if (message.reactions[1].count - 1) == fact_votes_needed:
                await message.channel.send("Fact has been rejected.")
                return
            if reaction.emoji == "✅":
                if (message.reactions[0].count - 1) == fact_votes_needed:
                    user_id = int(re.search(r'\[(\d+)\]', message.content).group(1))
                    user = get_user_by_id(user_id)
                    if user is None:
                        await message.channel.send("No user found with id [{user_id}]")
                        return
                    
                    fact = message.content.split("\r\r")[1]
                    if user.fact_exists(fact):
                        await message.channel.send("This fact already exists for {user.name} [{user_id}]")
                        return
                    user.add_fact(fact)
                    await message.channel.send("Fact has been added.")
                    
                    convo_message = f"\r\r{user.name}[{user.discord_id}] has had follwing fact updated about them. Say something about this.\r\r Fact:{fact}"
                    conversation.append({'role': 'user', 'content': convo_message})
                    await gpt_conversation(conversation)
                    await message.channel.send(conversation[-1]['content'].strip())
    except Exception as e:
        print(e)
        raise(e)


@bot.event
async def on_message(message):
    await bot.process_commands(message)
    if message.content.startswith('%') == False:
        if 'bro-bot' in message.content:
            user = get_user_by_id(message.author.id)
            user_message = f"{user.name}: {message.content}"
            conversation.append({'role': 'user', 'content': user_message})
            await gpt_conversation(conversation)
            channel = await bot.fetch_channel(message.channel.id)
            await channel.send(conversation[-1]['content'].strip())

@bot.event
async def on_voice_state_update(member, before, after):
    if before.channel != after.channel:
        if after.channel is not None:
            print(f'{member.name} joined {after.channel.name}')
            if after.channel.id == voice_channel_id:
                user = get_user_by_id(member.id)
                user.discord_info = member
                await send_user_greeting(user)
            # Member joined a voice channel
        elif before.channel is not None:
            # Member left a voice channel
            print(f'{member.name} left {before.channel.name}')
            if after.channel.id == voice_channel_id:
                user = get_user_by_id(member.id)
                user.discord_info = {}

@bot.listen()
async def on_ready():
    print("Bot ready!")
    voice_channel = await bot.fetch_channel(voice_channel_id)
    channel = await bot.fetch_channel(channel_id)
    members = voice_channel.members
    update_online_members(members)
    await gpt_conversation(conversation)
    await channel.send(conversation[-1]['content'].strip())

async def send_user_greeting(user):
    message = f"{user.name}[{user.discord_id}] joined the voice channel. Greet them."
    conversation.append({'role': 'user', 'content': message})
    await gpt_conversation(conversation)
    channel = await bot.fetch_channel(channel_id)
    await channel.send(conversation[-1]['content'].strip())


def update_online_member(member):
    for user in users:
        if member.id == user.discord_id:
            user.add_discord_info(member)
            continue

def update_online_members(members):
    for member in members:
        update_online_member(member)


if __name__ == '__main__':
    users = load_users_from_file()
    conversation.append({'role': 'system', 'content': create_initial_prompt(prompt, users)})
    loop = asyncio.get_event_loop()
    loop.create_task(bot.start(bot_token))
    loop.run_forever()