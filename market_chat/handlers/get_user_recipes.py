import json
from chat_bot_database import get_user_id, get_saved_recipes_for_user

async def handle_get_user_recipes(websocket, pool, username):
    user_id = await get_user_id(pool, username)
    if user_id:
        saved_recipes = await get_saved_recipes_for_user(pool, user_id)
        await websocket.send_text(json.dumps({
            'action': 'user_recipes_list',
            'recipes': saved_recipes
        }))
