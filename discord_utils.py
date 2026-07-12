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


async def remove_verified_role(discord_id: str) -> bool:
    if not all([DISCORD_GUILD_ID, DISCORD_VERIFIED_ROLE_ID, DISCORD_BOT_TOKEN]):
        logging.warning("Missing Discord environment variables for role removal.")
        return False

    url = f"https://discord.com/api/v10/guilds/{DISCORD_GUILD_ID}/members/{discord_id}/roles/{DISCORD_VERIFIED_ROLE_ID}"
    headers = {
        "Authorization": f"Bot {DISCORD_BOT_TOKEN}",
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.delete(url, headers=headers)
            if response.status_code == 204:
                return True
            else:
                logging.warning(f"Failed to remove role. Status: {response.status_code}, Body: {response.text}")
                return False
        except Exception as e:
            logging.warning(f"Error removing role: {e}")
            return False


async def send_dm(discord_id: str, message: str) -> bool:
    if not DISCORD_BOT_TOKEN:
        logging.warning("Missing Discord bot token for DM.")
        return False

    headers = {
        "Authorization": f"Bot {DISCORD_BOT_TOKEN}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient() as client:
        try:
            # Step 1: open a DM channel with the user
            dm_channel_resp = await client.post(
                "https://discord.com/api/v10/users/@me/channels",
                headers=headers,
                json={"recipient_id": discord_id}
            )
            if dm_channel_resp.status_code != 200:
                logging.warning(f"Failed to create DM channel. Status: {dm_channel_resp.status_code}, Body: {dm_channel_resp.text}")
                return False

            channel_id = dm_channel_resp.json().get("id")

            # Step 2: send the message to that channel
            message_resp = await client.post(
                f"https://discord.com/api/v10/channels/{channel_id}/messages",
                headers=headers,
                json={"content": message}
            )
            if message_resp.status_code == 200:
                return True
            else:
                logging.warning(f"Failed to send DM. Status: {message_resp.status_code}, Body: {message_resp.text}")
                return False
        except Exception as e:
            logging.warning(f"Error sending DM: {e}")
            return False