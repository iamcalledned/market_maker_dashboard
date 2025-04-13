from chat_bot_database import get_user_id, un_favorite_recipe

async def handle_remove_recipe(data_dict, pool, username):
    recipe_id = data_dict.get('content')
    userID = await get_user_id(pool, username)
    await un_favorite_recipe(pool, userID, recipe_id)
