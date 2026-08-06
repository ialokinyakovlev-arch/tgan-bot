import discord
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
import traceback

# ================= НАСТРОЙКИ БОТА =================
TOKEN = "MTUzNDkxMzE4MzEwODgyNTIyMQ.GxpWBv.iSwkTnIv1XhfNAPVpmcDgsXpQl37zztK5KzYs4"
CHANNEL_APPLICATIONS_ID = 1534930734815514674  # ID канала рекрутеров без кавычек
ROLE_ACCEPTED_IDS = [1509301959394594926]  # ID роли, которая выдается при ПРИНЯТИИ
ROLE_RECRUIT_ID = 1534920590656536747  # ID роли рекрутеров для тега
# ==================================================

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ВТОРАЯ ЧАСТЬ АНКЕТЫ (4 вопроса)
class ApplicationModalPart2(Modal, title="Заявка в loveSquad (Часть 2/2)"):
    cheat = TextInput(label="С каким читом вы играете?", placeholder="Название софта...", max_length=100)
    mic = TextInput(label="Имеете ли вы хороший микрофон?", placeholder="Да / Нет / Пойдет", max_length=50)
    hours = TextInput(label="Сколько часов можете проводить с нами?", placeholder="Например: 4-6 часов каждый день", max_length=100)
    tz = TextInput(label="Какой у вас часовой пояс?", placeholder="Например: МСК, МСК+2", max_length=50)

    def __init__(self, part1_data):
        super().__init__()
        self.part1_data = part1_data

    async def on_submit(self, interaction: discord.Interaction):
        # Моментально отвечаем пользователю, чтобы Discord не закрывал сессию
        await interaction.response.send_message("Ваша заявка успешно отправлена на рассмотрение!", ephemeral=True)
        
        try:
            guild = interaction.guild
            channel = bot.get_channel(CHANNEL_APPLICATIONS_ID)
            
            if not guild:
                print("[ОШИБКА] Бот не может найти сервер (guild равен None).")
                return
            if not channel:
                print(f"[ОШИБКА] Бот не может найти канал с ID {CHANNEL_APPLICATIONS_ID}. Проверьте правильность ID!")
                return

            # Имя пользователя для новых версий discord.py
            username = interaction.user.global_name if interaction.user.global_name else interaction.user.name

            # Собираем красивый эмбед из обеих частей анкеты
            embed = discord.Embed(title="New Application! | Новая заявка", color=discord.Color.blurple())
            embed.set_author(name=username, icon_url=interaction.user.display_avatar.url)
            
            # Данные из Части 1
            embed.add_field(name="Как вас зовут", value=self.part1_data['name'], inline=False)
            embed.add_field(name="Сколько вам лет (13+)", value=self.part1_data['age'], inline=False)
            embed.add_field(name="Ваша адекватность (от 0 до 10)", value=self.part1_data['adeq'], inline=False)
            embed.add_field(name="Насколько вы хороши в ХВХ (от 1 до 10)", value=self.part1_data['hvh'], inline=False)
            embed.add_field(name="Насколько вы хороши в PVE (от 1 до 10)", value=self.part1_data['pve'], inline=False)
            
            # Данные из Части 2
            embed.add_field(name="С каким читом вы играете", value=self.cheat.value, inline=False)
            embed.add_field(name="Имеете ли вы хороший микрофон?", value=self.mic.value, inline=False)
            embed.add_field(name="Сколько часов можете проводить с нами?", value=self.hours.value, inline=False)
            embed.add_field(name="Какой у вас часовой пояс?", value=self.tz.value, inline=False)
            
            embed.set_footer(text=f"User ID: {interaction.user.id}")

            view = RecruitDecisionView(applicant_id=interaction.user.id)
            
            # Простой и надежный тег роли через упоминание
            mention_text = f"<@&{ROLE_RECRUIT_ID}> Поступила новая заявка!"
            
            # Отправляем сообщение в чат
            await channel.send(content=mention_text, embed=embed, view=view)
            print("[УСПЕХ] Заявка успешно отправлена в канал!")

        except discord.Forbidden:
            print("[КРИТИЧЕСКАЯ ОШИБКА] У бота НЕТ ПРАВ на отправку сообщений или эмбедов в этот канал!")
        except Exception as e:
            print("[НЕИЗВЕСТНАЯ ОШИБКА] Произошел сбой при отправке:")
            traceback.print_exc()


# Промежуточная кнопка для вызова второй части анкеты
class NextPartView(View):
    def __init__(self, part1_data):
        super().__init__(timeout=300)
        self.part1_data = part1_data

    @discord.ui.button(label="Продолжить заполнение (Часть 2)", style=discord.ButtonStyle.blurple)
    async def next_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(ApplicationModalPart2(part1_data=self.part1_data))
        try:
            await interaction.delete_original_response()
        except Exception:
            pass


# ПЕРВАЯ ЧАСТЬ АНКЕТЫ (5 вопросов)
class ApplicationModalPart1(Modal, title="Заявка в loveSquad (Часть 1/2)"):
    name_input = TextInput(label="Как вас зовут", placeholder="Ваше имя...", max_length=50)
    age = TextInput(label="Сколько вам лет (13+)", placeholder="Ваш реальный возраст...", min_length=1, max_length=3)
    adeq = TextInput(label="Ваша адекватность (от 0 до 10)", placeholder="Оцените себя честно...", min_length=1, max_length=2)
    hvh = TextInput(label="Насколько вы хороши в ХВХ (от 1 до 10)", placeholder="Уровень игры...", min_length=1, max_length=2)
    pve = TextInput(label="Насколько вы хороши в PVE (от 1 до 10)", placeholder="Уровень игры...", min_length=1, max_length=2)

    async def on_submit(self, interaction: discord.Interaction):
        data = {
            'name': self.name_input.value,
            'age': self.age.value,
            'adeq': self.adeq.value,
            'hvh': self.hvh.value,
            'pve': self.pve.value
        }
        await interaction.response.send_message(
            "Отлично! Первая часть сохранена. Нажмите кнопку ниже, чтобы ответить на оставшиеся вопросы.", 
            view=NextPartView(part1_data=data), 
            ephemeral=True
        )


# Кнопка отправки анкеты в главном меню
class MainMenuView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Подать заявку в loveSquad", style=discord.ButtonStyle.green, custom_id="apply_btn")
    async def apply_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(ApplicationModalPart1())


# Кнопки для рекрутеров (Принять/Отклонить)
class RecruitDecisionView(View):
    def __init__(self, applicant_id: int):
        super().__init__(timeout=None)
        self.applicant_id = applicant_id

    @discord.ui.button(label="Принять", style=discord.ButtonStyle.success, custom_id="accept_btn")
    async def accept(self, interaction: discord.Interaction, button: Button):
        guild = interaction.guild
        member = guild.get_member(self.applicant_id)
        
        if not member:
            await interaction.response.send_message("Пользователь покинул сервер.", ephemeral=True)
            return

        roles_to_add = [guild.get_role(role_id) for role_id in ROLE_ACCEPTED_IDS if guild.get_role(role_id)]
        if roles_to_add:
            await member.add_roles(*roles_to_add)
            
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.green()
        embed.title = "Заявка ПРИНЯТА"
        embed.add_field(name="Вердикт", value=f"Принят рекрутером {interaction.user.mention}", inline=False)
        
        for child in self.children:
            child.disabled = True
            
        await interaction.response.edit_message(embed=embed, view=self)
        
        try:
            await member.send("Поздравляем! Ваша заявка в **loveSquad** была принята! Добро пожаловать.")
        except discord.Forbidden:
            pass

    @discord.ui.button(label="Отклонить", style=discord.ButtonStyle.danger, custom_id="reject_btn")
    async def reject(self, interaction: discord.Interaction, button: Button):
        guild = interaction.guild
        member = guild.get_member(self.applicant_id)

        embed = interaction.message.embeds[0]
        embed.color = discord.Color.red()
        embed.title = "Заявка ОТКЛОНЕНА"
        embed.add_field(name="Вердикт", value=f"Отклонен рекрутером {interaction.user.mention}", inline=False)

        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)

        if member:
            try:
                await member.send("К сожалению, ваша заявка в **loveSquad** была отклонена.")
            except discord.Forbidden:
                pass

@bot.event
async def on_ready():
    print(f"Бот запущен под именем {bot.user}")
    bot.add_view(MainMenuView())

@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    embed = discord.Embed(
        title="Набор в loveSquad open!",
        description="Хочешь стать частью нашей команды? Нажми на кнопку ниже и заполни небольшую анкету!",
        color=discord.Color.pink()
    )
    await ctx.send(embed=embed, view=MainMenuView())

bot.run(TOKEN)
