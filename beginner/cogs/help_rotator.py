from beginner.cog import Cog
from beginner.colors import *
from beginner.scheduler import schedule
from beginner.tags import tag
import datetime
import discord
import discord.ext.commands


class HelpRotatorCog(Cog):
    @property
    def available_category(self) -> discord.CategoryChannel:
        return self.get_category("Help: Available")

    @property
    def occupied_category(self) -> discord.CategoryChannel:
        return self.get_category("Help: Occupied")

    @Cog.listener()
    async def on_message(self, message: discord.Message):
        if self.is_available_python_help_channel(message.channel):
            await self.rotate_available_channels(message)
        elif self.is_occupied_python_help_channel(message.channel):
            await self.rotate_occupied_channels(message)

    @Cog.command("remind", aliases=["remind-me", "remindme"])
    async def remind(self, ctx: discord.ext.commands.Context, duration:str, *, message: str):
        minutes = 0
        hours = 0
        days = 0
        if duration.casefold().endswith("d"):
            days = int(duration[:-1])
        elif duration.casefold().endswith("h"):
            hours = int(duration[:-1])
        elif duration.casefold().endswith("m"):
            minutes = int(duration[:-1])
        elif duration.isdigit():
            minutes = int(duration)
        else:
            await ctx.send(f"{ctx.author.mention} durations must be of the format `123d`, `123h`, or `123m`/`123`.", delete_after=15)
            return

        if minutes < 1 and hours < 1 and days < 1:
            await ctx.send(f"{ctx.author.mention} cannot set a reminder for less than a minute", delete_after=15)
            return

        time_duration = datetime.timedelta(days=days, hours=hours, minutes=minutes)
        scheduled = schedule(f"reminder-{ctx.author.id}", time_duration, self.reminder_handler, message, ctx.message.id, ctx.channel.id, no_duplication=True)
        if scheduled:
            await ctx.send(f"{ctx.author.mention} a reminder has been set", delete_after=15)
        else:
            await ctx.send(f"{ctx.author.mention} you already have a reminder scheduled", delete_after=15)

    @tag("schedule", "reminder")
    async def reminder_handler(self, content: str, message_id: int, channel_id: int):
        channel: discord.TextChannel = self.server.get_channel(channel_id)
        message: discord.Message = await channel.fetch_message(message_id)
        author: discord.Member = message.author
        await channel.send(
            content=f"{author.mention}",
            embed=discord.Embed(
                description=content,
                color=BLUE
            ).set_author(name="Reminder ⏰")
        )

    @Cog.command("free-channel", aliases=["free"])
    async def free_channel(self, ctx: discord.ext.commands.Context):
        await ctx.send(f"Please use this free channel which is currently not in use:\n{self.available_category.channels[0].mention}")

    async def rotate_available_channels(self, message: discord.Message):
        # Rotate next occupied channel into active
        next_channel = self.get_next_channel()
        available_insert = self.get_channel("web-dev-help").position
        await next_channel.send(
            embed=discord.Embed(
                description="Feel free to ask any of your Python related questions in this channel!",
                color=GREEN
            ).set_author(name="This Channel Is Available", icon_url=self.server.icon_url)
        )
        await next_channel.edit(category=self.available_category, position=available_insert)

        # Rotate active channel to occupied
        current_top_occupied = self.occupied_category.channels[0].position
        await message.channel.edit(category=self.occupied_category, position=current_top_occupied)

    async def rotate_occupied_channels(self, message: discord.Message):
        current_top_occupied = self.occupied_category.channels[0].position
        await message.channel.edit(category=self.occupied_category, position=current_top_occupied)

    def get_next_channel(self) -> discord.TextChannel:
        return self.occupied_category.text_channels[-1]

    def is_available_python_help_channel(self, channel: discord.TextChannel) -> bool:
        if channel.category_id != self.available_category.id:
            return False

        return channel.name.startswith("python-help-")

    def is_occupied_python_help_channel(self, channel: discord.TextChannel) -> bool:
        if channel.category_id != self.occupied_category.id:
            return False

        return channel.name.startswith("python-help-")


def setup(client):
    client.add_cog(HelpRotatorCog(client))
