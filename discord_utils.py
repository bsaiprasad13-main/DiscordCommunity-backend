import os
import httpx
import asyncio
import logging
from dotenv import load_dotenv

load_dotenv()

DISCORD_GUILD_ID = os.getenv("DISCORD_GUILD_ID")
DISCORD_VERIFIED_ROLE_ID = os.getenv("DISCORD_VERIFIED_ROLE_ID")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")


async def assign_verified_role(discord_id: str, max_retries: int = 3) -> bool:
    if not all([DISCORD_GUILD_ID, DISCORD_VERIFIED_ROLE_ID, DISCORD_BOT_TOKEN]):
        logging.warning("Missing Discord environment variables for role assignment.")
        return False

    url = f"https://discord.com/api/v10/guilds/{DISCORD_GUILD_ID}/members/{discord_id}/roles/{DISCORD_VERIFIED_ROLE_ID}"
    headers = {
        "Authorization": f"Bot {DISCORD_BOT_TOKEN}",
        "Content-Length": "0"
    }

    async with httpx.AsyncClient() as client:
        for attempt in range(max_retries + 1):
            try:
                response = await client.put(url, headers=headers)

                if response.status_code == 204:
                    return True

                if response.status_code == 429:
                    retry_after = response.json().get("retry_after", 1)
                    logging.warning(f"Rate limited assigning role. Retrying after {retry_after}s (attempt {attempt + 1}).")
                    await asyncio.sleep(retry_after)
                    continue

                logging.warning(f"Failed to assign role. Status: {response.status_code}, Body: {response.text}")
                return False

            except Exception as e:
                logging.warning(f"Error assigning role: {e}")
                return False

    logging.warning(f"Exhausted retries assigning role to {discord_id}.")
    return False


async def remove_verified_role(discord_id: str, max_retries: int = 3) -> bool:
    if not all([DISCORD_GUILD_ID, DISCORD_VERIFIED_ROLE_ID, DISCORD_BOT_TOKEN]):
        logging.warning("Missing Discord environment variables for role removal.")
        return False

    url = f"https://discord.com/api/v10/guilds/{DISCORD_GUILD_ID}/members/{discord_id}/roles/{DISCORD_VERIFIED_ROLE_ID}"
    headers = {
        "Authorization": f"Bot {DISCORD_BOT_TOKEN}",
    }

    async with httpx.AsyncClient() as client:
        for attempt in range(max_retries + 1):
            try:
                response = await client.delete(url, headers=headers)

                if response.status_code == 204:
                    return True

                if response.status_code == 429:
                    retry_after = response.json().get("retry_after", 1)
                    logging.warning(f"Rate limited removing role. Retrying after {retry_after}s (attempt {attempt + 1}).")
                    await asyncio.sleep(retry_after)
                    continue

                logging.warning(f"Failed to remove role. Status: {response.status_code}, Body: {response.text}")
                return False

            except Exception as e:
                logging.warning(f"Error removing role: {e}")
                return False

    logging.warning(f"Exhausted retries removing role from {discord_id}.")
    return False


async def send_dm(discord_id: str, message: str, max_retries: int = 3) -> bool:
    if not DISCORD_BOT_TOKEN:
        logging.warning("Missing Discord bot token for DM.")
        return False

    headers = {
        "Authorization": f"Bot {DISCORD_BOT_TOKEN}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient() as client:
        # Step 1: open a DM channel with the user (with retry)
        channel_id = None
        for attempt in range(max_retries + 1):
            try:
                dm_channel_resp = await client.post(
                    "https://discord.com/api/v10/users/@me/channels",
                    headers=headers,
                    json={"recipient_id": discord_id}
                )

                if dm_channel_resp.status_code == 200:
                    channel_id = dm_channel_resp.json().get("id")
                    break

                if dm_channel_resp.status_code == 429:
                    retry_after = dm_channel_resp.json().get("retry_after", 1)
                    logging.warning(f"Rate limited creating DM channel. Retrying after {retry_after}s (attempt {attempt + 1}).")
                    await asyncio.sleep(retry_after)
                    continue

                logging.warning(f"Failed to create DM channel. Status: {dm_channel_resp.status_code}, Body: {dm_channel_resp.text}")
                return False

            except Exception as e:
                logging.warning(f"Error creating DM channel: {e}")
                return False

        if channel_id is None:
            logging.warning(f"Exhausted retries creating DM channel for {discord_id}.")
            return False

        # Step 2: send the message to that channel (with retry)
        for attempt in range(max_retries + 1):
            try:
                message_resp = await client.post(
                    f"https://discord.com/api/v10/channels/{channel_id}/messages",
                    headers=headers,
                    json={"content": message}
                )

                if message_resp.status_code == 200:
                    return True

                if message_resp.status_code == 429:
                    retry_after = message_resp.json().get("retry_after", 1)
                    logging.warning(f"Rate limited sending DM. Retrying after {retry_after}s (attempt {attempt + 1}).")
                    await asyncio.sleep(retry_after)
                    continue

                logging.warning(f"Failed to send DM. Status: {message_resp.status_code}, Body: {message_resp.text}")
                return False

            except Exception as e:
                logging.warning(f"Error sending DM: {e}")
                return False

    logging.warning(f"Exhausted retries sending DM to {discord_id}.")
    return False