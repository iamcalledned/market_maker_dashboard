import json
from chat_bot_database import get_recipe_for_printing

async def handle_print_recipe(websocket, data_dict, pool):
    recipe_id = data_dict.get('content')
    print_result = await get_recipe_for_printing(pool, recipe_id)
    await websocket.send_text(json.dumps({'action': 'recipe_printed', 'data': print_result}))
