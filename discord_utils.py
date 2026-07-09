import os
import httpx
import logging
from dotenv import load_dotenv

load_dotenv()

DISCORD_GUILD_ID = os.getenv("DISCORD_GUILD_ID")
DISCORD_VERIFIED_ROLE_ID = os.getenv("DISCORD_VERIFIED_ROLE_ID")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

async def assign_verified_role(discord_id: str) -> bool:
    if not all([DISCORD_GUILD_ID, DISCORD_VERIFIED_ROLE_ID, DISCORD_BOT_TOKEN]):
        logging.warning("Missing Discord environment variables for role assignment.")
        return False

    url = f"https://discord.com/api/v10/guilds/{DISCORD_GUILD_ID}/members/{discord_id}/roles/{DISCORD_VERIFIED_ROLE_ID}"
    headers = {
        "Authorization": f"Bot {DISCORD_BOT_TOKEN}",
        "Content-Length": "0"
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.put(url, headers=headers)
            if response.status_code == 204:
                return True
            else:
                logging.warning(f"Failed to assign role. Status: {response.status_code}, Body: {response.text}")
                return False
        except Exception as e:
            logging.warning(f"Error assigning role: {e}")
            return False
