# openai_utils_send_message.py

from openai import AsyncOpenAI
from config import Config

# Initialize Async OpenAI client
openai_client = AsyncOpenAI(api_key=Config.OPENAI_API_KEY)

# Send message to thread
async def send_message(thread_id_n, message):
    try:
        response = await openai_client.beta.threads.messages.create(
            thread_id=thread_id_n,
            role="user",
            content=message
        )

        # Return raw Markdown response text
        return response.content[0].text.value

    except Exception as e:
        print(f"Error in sending message: {e}")
        return "Error in sending message."
