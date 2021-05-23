import re
from datetime import datetime, timedelta
from discord import Embed, Guild, Message, RawReactionActionEvent, TextChannel, errors
from extensions.kudos.manager import KudosManager
from extensions.help_channels.channel_manager import ChannelManager
from itertools import islice
import dippy


FIRST_TIME_BONUS = 32
DAILY_MESSAGE_BONUS = 4
WEEKLY_STREAK_BONUS = 16


class KudosExtension(dippy.Extension):
    client: dippy.Client
    log: dippy.logging.Logging
    manager: KudosManager
    help_channels: ChannelManager

    @dippy.Extension.listener("ready")
    async def ready_(self):
        channel = self.client.get_channel(846164230058672209)
        emoji = await self.manager.get_kudos_emoji(channel.guild)
        await channel.send(
            embed=Embed(
                title="Kudos",
                description=(
                    "You can give people kudos by reacting to their message with these emoji:\n"
                    + (
                        "\n".join(
                            f"{self.manager.get_emoji(channel.guild, emoji)} {points} kudos"
                            for emoji, points in emoji.items()
                        )
                    )
                    + "\nYou can also earn kudos by sending one message every day (UTC) and maintaining that streak."
                ),
                color=0x4285F4,
            ).set_thumbnail(url=self.manager.get_emoji(channel.guild, "expert").url)
        )

    @dippy.Extension.command("!kudos leaderboard")
    async def get_kudos_leaderboard(self, message: Message):
        leaders = await self.manager.get_leaderboard(message.guild)
        user_kudos = leaders.get(message.author)
        if user_kudos is None:
            user = await self.manager.get_kudos(message.author)

        leaderboard = []
        for index, (member, member_kudos) in islice(
            enumerate(leaders.items(), start=1), 0, 5
        ):
            name = member.display_name if member else "*Old Member*"
            entry = f"{index}. {name} has {member_kudos} kudos"
            if member == message.author:
                entry = f"**{entry}**"
            leaderboard.append(entry)

        embed = (
            Embed(
                color=0x4285F4,
                description=f"{message.author.mention} you have {user_kudos if user_kudos > 0 else 'no'} kudos",
                title="Kudos Leaderboard",
            )
            .set_thumbnail(
                url="https://cdn.discordapp.com/emojis/669941420454576131.png?v=1"
            )
            .add_field(name="Leader Board", value="\n".join(leaderboard), inline=False)
        )
        await message.channel.send(embed=embed)

    @dippy.Extension.command("!import kudos")
    async def import_kudos(self, message: Message):
        if not message.author.guild_permissions.manage_channels:
            return

        for line in (await message.attachments[0].read()).strip().split(b"\n"):
            try:
                member_id, points = map(int, line.split(b","))
            except ValueError:
                print("FAILED", line)
            else:
                member = message.guild.get_member(member_id)
                if not member:
                    try:
                        member = await message.guild.fetch_member(member_id)
                    except errors.NotFound:
                        await message.channel.send(
                            f"{member_id} is no longer a member, they had {points} kudos"
                        )
                        continue
                await self.manager.set_kudos(member, points)
                await message.channel.send(
                    f"{member.display_name} now has {points} kudos"
                )

    @dippy.Extension.command("!set kudos ledger")
    async def set_kudos_ledger_channel(self, message: Message):
        if not message.author.guild_permissions.manage_channels:
            return

        channel_id, *_ = re.match(r".+?<#(\d+)>", message.content).groups()
        channel = self.client.get_channel(int(channel_id))
        await self.manager.set_ledger_channel(channel)
        await channel.send("This is now the Kudos Ledger!")

    @dippy.Extension.command("!set kudos emoji")
    async def set_kudos_emoji(self, message: Message):
        if not message.author.guild_permissions.manage_channels:
            return

        emoji = {
            name: int(value)
            for name, value in re.findall(
                r"(?:<:)?(\S+?)(?::\d+>)? (\d+)", message.content
            )
        }
        await self.manager.set_kudos_emoji(message.guild, emoji)
        await message.channel.send(
            f"Set kudos emoji\n{self._build_emoji(message.guild, emoji)}"
        )

    @dippy.Extension.command("!get kudos emoji")
    async def get_kudos_emoji(self, message: Message):
        emoji = await self.manager.get_kudos_emoji(message.guild)
        if emoji:
            await message.channel.send(self._build_emoji(message.guild, emoji))
        else:
            await message.channel.send("*No kudos emoji are set*")

    @dippy.Extension.listener("raw_reaction_add")
    async def on_reaction(self, payload: RawReactionActionEvent):
        if payload.member.bot:
            return

        channel: TextChannel = self.client.get_channel(payload.channel_id)
        emoji = await self.manager.get_kudos_emoji(channel.guild)
        if not emoji:
            return

        if payload.emoji.name not in emoji:
            return

        archive_category = (await self.help_channels.get_categories(channel.guild)).get(
            "help-archive"
        )
        if (
            not channel.permissions_for(payload.member).send_messages
            and channel.category != archive_category
        ):
            return

        message = await channel.fetch_message(payload.message_id)
        if message.author.bot or message.author == payload.member:
            return

        kudos = await self.manager.get_kudos(payload.member)
        giving = emoji[payload.emoji.name]
        if giving > kudos:
            await channel.send(
                f"{payload.member.mention} you can't give {giving} kudos, you only have {kudos}",
                delete_after=15,
            )
            return

        await self.manager.give_kudos(
            message.author,
            giving,
            f"{payload.member.mention} gave {message.author.mention} kudos",
        )
        await self.manager.take_kudos(payload.member, giving)
        await channel.send(
            f"{payload.member.mention} you gave {message.author.display_name} {giving} kudos, you have {kudos - giving}"
            f" left to give.",
            reference=message,
            mention_author=False,
            delete_after=15,
        )

    @dippy.Extension.listener("message")
    async def on_message(self, message: Message):
        if (
            message.author.bot
            or not isinstance(message.channel, TextChannel)
            or message.author.pending
        ):
            return

        last_active_date = await self.manager.get_last_active_date(message.author)
        current_date = datetime.utcnow().date()
        if last_active_date == current_date:
            return

        await self.manager.set_last_active_date(message.author)
        current_streak, best_streak = await self.manager.get_streaks(message.author)

        kudos = DAILY_MESSAGE_BONUS
        reason = f"{message.author.mention} has sent their first message of the day!"
        if best_streak == 0:
            kudos = FIRST_TIME_BONUS
            reason = f"{message.author.mention} has joined the server!!!"
            await self.manager.set_streak(message.author, 1)

        elif last_active_date == current_date - timedelta(days=1):
            current_streak += 1
            await self.manager.set_streak(message.author, current_streak)

            if current_streak % 7 == 0:
                kudos = WEEKLY_STREAK_BONUS
                weeks = current_streak // 7
                reason = f"{message.author.mention} has messaged every day for {weeks} week{'s' * (weeks > 1)}!"

        await self.manager.give_kudos(message.author, kudos, reason)

    def _build_emoji(self, guild: Guild, emoji: dict[str, int]) -> str:
        return "\n".join(
            f"{self.manager.get_emoji(guild, name)} {value}"
            for name, value in sorted(emoji.items(), key=lambda item: item[1])
        )