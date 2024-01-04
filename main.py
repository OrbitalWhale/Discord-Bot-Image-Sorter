import discord
import os
import sys
import logging
import datetime
import hashlib
from PIL import Image
from discord.ext import commands
from discord.ui import View, Button


HASHES_FILE = 'hashes.txt'
logging.basicConfig(filename='app.log', format='%(asctime)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', level=logging.INFO)

logging.info('Starting bot ...')
# logging.warning('This is a warning message')
# logging.error('This is an error message')

class ConfirmButton(Button):
    def __init__(self, ctx, embed):
        super().__init__(label='Yes', style=discord.ButtonStyle.green, custom_id='confirm')
        self.ctx = ctx
        self.embed = embed

    async def callback(self, interaction: discord.Interaction):
        self.view.confirm.disabled = True
        self.view.deny.disabled = True
        await interaction.response.edit_message(view=self.view, embed=self.embed, delete_after=1)
        await self.ctx.channel.send(f'{self.ctx.author} posted: {self.ctx.attachments[0].url}')

class DenyButton(Button):
    def __init__(self, ctx, embed):
        super().__init__(label='No', style=discord.ButtonStyle.red)
        self.ctx = ctx
        self.embed = embed

    async def callback(self, interaction: discord.Interaction):
        self.view.confirm.disabled = True
        self.view.deny.disabled = True
        await interaction.response.edit_message(view=self.view, embed=self.embed, delete_after=1)
        os.remove(self.ctx.attachments[0].filename)

class ConfirmView(View):
    def __init__(self, ctx, embed):
        super().__init__()
        self.ctx = ctx
        self.embed = embed
        self.confirm = ConfirmButton(ctx, embed)
        self.deny = DenyButton(ctx, embed)
        self.add_item(self.confirm)
        self.add_item(self.deny)

class ConfirmEmbed(discord.Embed):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.color = discord.Color.yellow()
        self.title = 'Confirm'
        self.add_field(name='Description', value=f'@{ctx.author} This photo is a duplicate. Do you want to post it anyway?')
        self.set_image(url=ctx.attachments[0].url)
        self.set_footer(text='This message will be deleted in 30 seconds.')

class ImageBot(commands.Bot):
    def __init__(self, command_prefix):
        intents = discord.Intents.default()
        intents.message_content = True
        
        super().__init__(command_prefix=command_prefix, intents=intents)

    async def on_ready(self):
        print(f'We have logged in as {self.user}')
        logging.info(f'We have logged in as {self.user}')

    async def on_message(self, message):
        if message.attachments:
            for attachment in message.attachments:
                await attachment.save(attachment.filename)
                logging.info(f'Attachment saved: {attachment.filename}')
                # TODO confirm attachment is an image
                print(attachment.content_type())
                if attachment.content_type() == 'image':
                    # TODO: Come up with a better way to identify images that is more robust than just the hash
                    image_hash = self.get_image_hash(attachment.filename)
                else:
                    logging.warning(f'Attachment is not an image: {attachment.filename}')
                    # Stop processing this message
                    continue
                
                if not self.is_duplicate(image_hash):
                    os.rename(attachment.filename, f'images/{image_hash}.{os.path.splittext(attachment.filename)}')
                    # os.rename(attachment.filename, f'images/{image_hash}.{attachment.filename.split(".")[-1]}')
                    self.save_hash(image_hash)
                else:
                    # Delete the message
                    await message.delete()
                    # Start an interaction with the user
                    embed = ConfirmEmbed(message)
                    # await message.channel.send(, delete_after=30)
                    view = ConfirmView(message, embed=embed)
                    await message.channel.send(embed=embed, view=view, delete_after=30)
                    
                    #### Retain this code for reference in case we want to send a DM instead of a channel message
                    # view = ConfirmView(message.author)
                    # await message.author.send(f'This image is a duplicate. Do you want to post it anyway? {attachment.url}', view=view)

        elif message.content.startswith(self.command_prefix):
            await self.process_commands(message)
            

    def get_image_hash(self, filename):
        with Image.open(filename) as img:
            return hashlib.md5(img.tobytes()).hexdigest()

    def is_duplicate(self, image_hash):
        if not os.path.exists(HASHES_FILE):
            with open(HASHES_FILE, 'a') as f:
                f.close()
        with open(HASHES_FILE, 'r') as f:
            hashes = f.read().splitlines()
        return image_hash in hashes
    
    def save_hash(self, image_hash):
        with open(HASHES_FILE, 'a') as f:
            f.write(image_hash + '\n')

if not os.path.exists('config.py'):
    logging.error('config.py file does not exist.')
    token = input('What is the bot token? ')
    with open('config.py', 'w') as f:
        f.write('class channel_ids:\n')
        f.write('    channel = \'insert channel id here\'\n')
        f.write('\n')
        f.write(f'bot_token = \'{token}\'')
    logging.info('config.py file created.')
    print('config.py file created.')
    print('Please edit the config.py file and add the channel ids manually.')
    print('Or run !admin_setup to set up the bot.')
    sys.exit()
else:
    #Throws a problem in vsc if the file doesn't exist yet. Can be ignored.
    from config import bot_token

# Code execution starts here
bot = ImageBot(command_prefix='!')

@bot.command()
async def ping(ctx):
    await ctx.send('pong')

@bot.command()
async def admin_setup(ctx):
    logging.info('Starting admin setup ...')
    channel_ids = {}
    await ctx.message.delete()
    for guild in bot.guilds:
        for channel in guild.channels:
            if channel.type == discord.ChannelType.text:
                print(f'Do you want to use this channel? {channel.name}')
                answer = input('y/n: ')
                if answer == 'y':
                    channel_ids[channel.name] = channel.id
    print(channel_ids)
    
    # Save the channel ids to the config.py file under the channel_ids class
    with open('config.py', 'r') as f:
        lines = f.readlines()
    with open('config.py', 'w') as f:
        for line in lines:
            if line.startswith('class channel_ids'):
                f.write(line)
                for key, value in channel_ids.items():
                    if key not in lines:
                        f.write(f'    {key} = {value}\n')
                    else:
                        print(f'{key} already exists in config.py')
            elif line.strip() == 'channel = \'insert channel id here\'':
                # Delete this line as it is no longer needed
                f.write('')
            else:
                f.write(line)
    logging.info('config.py file updated.')

bot.run(bot_token)