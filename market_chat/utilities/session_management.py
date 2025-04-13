import asyncio
import json

async def clear_session_data_after_timeout(session_id, username, redis_client, pool):
    try:
        await asyncio.sleep(3600)  # wait an hour before cleaning
        # Check if the session still exists before clearing
        if redis_client.exists(session_id):
            redis_client.delete(session_id)
            await clear_user_session_id(pool, session_id)
            print(f"Session data cleared for user {username}")

            # Send a WebSocket message to the client to log out
            if username in connections:
                websocket = connections[username]
                await websocket.send_text(json.dumps({'action': 'force_logout'}))
    except Exception as e:
        print(f"Error in session cleanup task for {username}: {e}")
