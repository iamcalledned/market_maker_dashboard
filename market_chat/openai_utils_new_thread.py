#openai_utils_new_thread.py
from openai import OpenAI
import sys
import os
# Get the directory of the current script
current_script_path = os.path.dirname(os.path.abspath(__file__))
# Set the path to the parent directory (one folder up)
parent_directory = os.path.dirname(current_script_path)
# Add the config directory to sys.path
sys.path.append(os.path.join(parent_directory, 'database'))
sys.path.append(os.path.join(parent_directory, 'config'))
from config import Config

OPENAI_API_KEY = Config.OPENAI_API_KEY



# Initialize OpenAI client
openai_client = OpenAI()
openai_client.api_key = Config.OPENAI_API_KEY

async def create_thread_in_openai():
    try:
        thread_response = openai_client.beta.threads.create()
        thread_id_n = thread_response.id
        #print("Created new thread ID:", thread_id_n)
        return thread_id_n
    except Exception as e:
        print(f"Error in creating thread: {e}")
        return None

async def is_thread_valid(thread_id):
    #print("tring to find thread for:", thread_id)
    try:
        #print("trying....")
        my_thread = openai_client.beta.threads.retrieve(thread_id)
        
        # Add your logic here based on how OpenAI's response indicates a valid thread.
        # This might depend on the response structure. For example:
        # return 'status' in my_thread and my_thread.status == 'active'
        #print("my thread", my_thread)
        return True  # Assuming the thread is valid if no exception occurred
    except Exception as e:
        print(f"Error checking thread validity: {e}")
        return False

async def get_thread_contents (thread_id):
    
    try:
        messages =openai_client.beta.threads.messages.list(thread_id)
        messages_list = list(messages)
        reversed_messages = reversed(messages_list)
        
        filtered_messages = [msg for msg in reversed_messages if msg.role in ['user', 'assistant']]

        last_five_messages = filtered_messages[:5]
        
        
        return messages
    except Exception as e:
        print(f"Error retrieving messages: {e}")
        return None
