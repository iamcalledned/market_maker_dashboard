# generate_answer.py
import time
import sys
import os
import markdown2
import datetime
import logging
import asyncio
import aiomysql
import re

# Get the directory of the current script
current_script_path = os.path.dirname(os.path.abspath(__file__))
parent_directory = os.path.dirname(current_script_path)
sys.path.append(os.path.join(parent_directory, 'database'))
sys.path.append(os.path.join(parent_directory, 'config'))

from openai_utils_new_thread import create_thread_in_openai, is_thread_valid, get_thread_contents
from openai_utils_send_message import send_message
from openai import OpenAI

from chat_bot_database import get_active_thread_for_user, insert_thread, insert_conversation, create_db_pool, get_user_id
from config import Config
from classify_content import classify_content

OPENAI_API_KEY = Config.OPENAI_API_KEY
log_file_path = '/home/ned/projects/whattogrill/chatbot-with-login/generate_answer_logs.txt'

logging.basicConfig(
    filename=log_file_path,
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

client = OpenAI(api_key=OPENAI_API_KEY)

async def generate_answer(pool, username, message, user_ip, uuid):
    recipe_id = None
    userID = await get_user_id(pool, username)
    print("Generating an answer for userID", userID, "username", username)

    active_thread = await get_active_thread_for_user(pool, userID)
    thread_id_n = None

    if active_thread:
        thread_id_n = active_thread['ThreadID']
        if thread_id_n and not await is_thread_valid(thread_id_n):
            thread_id_n = await create_thread_in_openai()
            await insert_thread(pool, thread_id_n, userID, True, datetime.datetime.now().isoformat())
    else:
        thread_id_n = await create_thread_in_openai()
        await insert_thread(pool, thread_id_n, userID, True, datetime.datetime.now().isoformat())

    await get_thread_contents(thread_id_n)

    if thread_id_n:
        response_text = await send_message(thread_id_n, message)
        run = client.beta.threads.runs.create(
            thread_id=thread_id_n,
            assistant_id="asst_cN5EMfahI1Xs9LwaAGxGR7a1"
        )

        print('run create')
        if run:
            await insert_conversation(pool, userID, thread_id_n, run.id, message, 'user', user_ip)
            print('inserted')

            while True:
                run = client.beta.threads.runs.retrieve(thread_id=thread_id_n, run_id=run.id)
                if run.status in ["completed", "error"]:
                    break
                await asyncio.sleep(1)

            messages = client.beta.threads.messages.list(thread_id=thread_id_n)
            message_content = messages.data[0].content[0].text.value

            # Convert Markdown to HTML
            html = markdown2.markdown(message_content)
            styled_html = f'<div class="prose max-w-none">{html}</div>'

            await insert_conversation(pool, userID, thread_id_n, run.id, message_content, 'bot', None)

            return styled_html, recipe_id
        else:
            print("Failed to create a run object in OpenAI.")
            return "Error: Failed to create a run object.", None

    return "Error: Failed to create a new thread in OpenAI.", None