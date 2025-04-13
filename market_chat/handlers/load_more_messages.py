import json
from chat_bot_database import get_user_id, get_messages_before

async def handle_load_more_messages(websocket, data_dict, pool, username):
    userID = await get_user_id(pool, username)
    last_loaded_timestamp = data_dict.get('last_loaded_timestamp')
    older_messages = await get_messages_before(pool, userID, last_loaded_timestamp)
    await websocket.send_text(json.dumps({
        'action': 'older_messages',
        'messages': older_messages
    }))
