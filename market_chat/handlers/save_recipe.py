import json
from chat_bot_database import favorite_recipe, get_user_id

async def handle_save_recipe(websocket, data_dict, pool, username):
    userID = await get_user_id(pool, username)
    recipe_id = data_dict.get('content')
    save_result = await favorite_recipe(pool, userID, recipe_id)
    if save_result == 'Success':
        save_result = 'success'
    await websocket.send_text(json.dumps({'action': 'recipe_saved', 'status': save_result}))
