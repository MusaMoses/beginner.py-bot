from beginner.cog import Cog
from beginner.colors import *
from beginner.history_queue import HistoryQueue
from beginner.scheduler import schedule
from beginner.tags import tag
from datetime import timedelta, datetime
import asyncio
import discord
import random


class OnBoarding(Cog):
    def __init__(self, client):
        super().__init__(client)
        self._disabled_welcome_messages = None
        self._join_history = HistoryQueue(timedelta(minutes=10))

    async def ready(self):
        await self.scan_for_unwelcomed_members()

    @Cog.listener()
    async def on_member_update(
        self, old_member: discord.Member, updated_member: discord.Member
    ):
        if updated_member.pending or not old_member.pending:
            return

        self._join_history.add(updated_member)
        await self.monitor_for_mass_join()

        five_minutes_ago = datetime.utcnow() - timedelta(minutes=5)
        if (
            not self._disabled_welcome_messages
            or self._disabled_welcome_messages < five_minutes_ago
        ):
            await self.welcome_member(updated_member)

    def under_mass_attack(self):
        minute_ago = datetime.utcnow() - timedelta(minutes=1)
        total_joins = 0
        for joined, member in self._join_history:
            if joined >= minute_ago:
                total_joins += 1

        return total_joins >= 4

    async def monitor_for_mass_join(self):
        if self.under_mass_attack():
            mods = self.get_role("mods")
            await self.get_channel("staff").send(
                f"{mods.mention} We may be experiencing a mass join attack. Disabling welcome messages for 5 minutes."
            )
            self._disabled_welcome_messages = datetime.utcnow()

    async def scan_for_unwelcomed_members(self):
        self.logger.debug("Scanning for unwelcomed members")
        members = [
            member
            for member in self.server.members
            if not member.pending and len(member.roles) == 1
        ]
        if not members:
            self.logger.debug("All members have been welcomed")
            return

        self.logger.debug(f"{len(members)} have not been welcomed")
        await self.get_channel("staff").send(
            f"I just restarted and found {len(members)} who accepted the rules while I was away. I'll welcome them now."
        )

        for member in members:
            await self.welcome_member(member)
            await asyncio.sleep(1)

    async def welcome_member(self, member: discord.Member):
        self.logger.debug(f"Welcoming {member.display_name}")
        welcome_messages = [
            "Everybody say hi to {}!!!",
            "Say hello to our newest member {}!!!",
            "Welcome to our newest & coolest member {}!!!",
            "Hey hey hey!!! {} has joined the party!!!",
        ]
        message = random.choice(welcome_messages).format(member.mention)
        wolf_wave_emoji = discord.utils.get(self.client.emojis, name="wolfwave")
        await self.get_channel("🙋hello-world").send(f"{wolf_wave_emoji} {message}")

        await member.add_roles(self.get_role("member"))


def setup(client):
    client.add_cog(OnBoarding(client))
