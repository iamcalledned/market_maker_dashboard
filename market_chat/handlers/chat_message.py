import json
from uuid import uuid4
from openai_utils_generate_answer import generate_answer

async def handle_chat_message(websocket, data_dict, pool, username, client_ip):
    message = data_dict.get('message', '')
    uuid = str(uuid4())
    response_text, content_type, recipe_id = await generate_answer(pool, username, message, client_ip, uuid)
    response = {
        'response': response_text,
        'type': content_type,
        'recipe_id': recipe_id
    }
    await websocket.send_text(json.dumps(response))
