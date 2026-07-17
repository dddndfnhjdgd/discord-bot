import discord
import os
import asyncio
from dotenv import load_dotenv
import yt_dlp
from collections import deque

# تحميل المتغيرات من ملف .env
load_dotenv()

TOKEN = os.getenv("TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

# إعدادات yt-dlp لـ جلب الصوت فقط وبأفضل جودة
YDL_OPTIONS = {
    'format': 'bestaudio/best',
    'quiet': True,
    'default_search': 'ytsearch1',
    'noplaylist': True
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

class MyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_volume = 0.5  # مستوى الصوت الافتراضي
        self.queue = deque()  # قائمة التشغيل
        self.now_playing = None  # المقطع الحالي
        self.song_loop = False  # تكرار المقطع (عدلنا الاسم لمنع التعارض)

    async def play_next(self, guild):
        """تشغيل المقطع التالي في القائمة"""
        voice_client = guild.voice_client
        if not voice_client:
            return
        
        if self.song_loop and self.now_playing:
            # وضع التكرار: يشغل نفس المقطع مرة ثانية
            await self.play_song(guild, self.now_playing['url'], self.now_playing['title'])
        elif self.queue:
            # فيه مقاطع في القائمة
            next_song = self.queue.popleft()
            await self.play_song(guild, next_song['url'], next_song['title'])
        else:
            self.now_playing = None

    async def play_song(self, guild, url, title):
        """تشغيل مقطع محدد باستخدام ملف ffmpeg المحلي"""
        voice_client = guild.voice_client
        if not voice_client:
            return
        
        # تخزين معلومات المقطع الحالي
        self.now_playing = {'url': url, 'title': title}
        
        # تشغيل المقطع وتحديد مسار الـ exe المحلي لضمان عدم التعارض
        source = discord.FFmpegPCMAudio(url, executable="ffmpeg.exe", **FFMPEG_OPTIONS)
        source = discord.PCMVolumeTransformer(source, volume=self.current_volume)
        
        # استدعاء حلقة بايثون الحقيقية بشكل صحيح لمنع تجمد الأوامر
        client_loop = self.loop 
        
        def after_playing(error):
            if error:
                print(f"خطأ في التشغيل: {error}")
            # تشغيل المقطع التالي بعد الانتهاء بأمان
            asyncio.run_coroutine_threadsafe(self.play_next(guild), client_loop)
        
        voice_client.play(source, after=after_playing)

    async def on_ready(self):
        print(f'✅ الحساب متصل: {self.user}')
        print(f'✅ تم تسجيل الدخول بنجاح')
        # تشغيل حلقة التثبيت بالروم في الخلفية لضمان بقائه 24 ساعة
        self.loop.create_task(self.keep_alive())

    async def keep_alive(self):
        """تثبيت الحساب داخل الروم الصوتي ومنعه من الخروج"""
        await self.wait_until_ready()
        while not self.is_closed():
            try:
                guild = self.get_guild(GUILD_ID)
                if guild:
                    voice_client = guild.voice_client
                    
                    # فحص دقيق عبر السيرفر للتأكد إذا كان الحساب متصل فعلياً
                    if not voice_client or not voice_client.is_connected():
                        channel = self.get_channel(CHANNEL_ID)
                        if channel:
                            await channel.connect(self_mute=False, self_deaf=False)
                            print(f"📡 دخلت الروم الصوتي وثبت فيه: {channel.name}")
                    else:
                        # إذا كان متصل بالروم، نتأكد أنه في الروم الصحيح المكتوب بالـ .env
                        if voice_client.channel.id != CHANNEL_ID:
                            channel = self.get_channel(CHANNEL_ID)
                            if channel:
                                print(f"🔄 الحساب في روم خطأ، جاري نقله للروم المحدد...")
                                await voice_client.move_to(channel)
            except Exception as e:
                print(f"⚠️ خطأ في البقاء: {e}")
            
            # فحص كل 15 ثانية لضمان ثبات تام 24 ساعة
            await asyncio.sleep(15)

    async def on_message(self, message):
        # تجاهل الرسائل المرسلة من نفس الحساب لعدم تكرار الأوامر بشكل لانهائي
        if message.author == self.user:
            return
        
        if message.channel.id != CHANNEL_ID:
            return
        
        content = message.content.strip().lower()
        guild = message.guild
        
        # ========== قائمة الأوامر (مساعدة) ==========
        if content in ['الاوامر', 'help', 'اوامر', 'قائمة الاوامر', 'h']:
            help_text = """
📋 **قائمة الأوامر:**

🎵 **التشغيل والتحكم:**
`ش <اسم المقطع>` - تشغيل مقطع من يوتيوب
`وقف` أو `stop` - إيقاف التشغيل
`ت` أو `skip` - تخطي المقطع الحالي
`بـ` أو `pause` - إيقاف مؤقت
`كمل` أو `resume` - استئناف التشغيل

🔄 **القائمة والتكرار:**
`كرر` أو `loop` - تفعيل/إلغاء تكرار المقطع
`قائمة` أو `queue` - عرض قائمة التشغيل
`مسح` أو `clear` - مسح قائمة التشغيل

🔊 **الصوت:**
`ص <0-100>` - تغيير مستوى الصوت

🚪 **الخروج:**
`اخرج` أو `leave` - الخروج من الروم الصوتي

📌 **اختصارات انجليزية:**
`p <query>` - Play (تشغيل)
`s` - Stop (إيقاف)
`sk` - Skip (تخطي)
`pa` - Pause (إيقاف مؤقت)
`re` - Resume (استئناف)
`l` - Loop (تكرار)
`q` - Queue (قائمة التشغيل)
`v <0-100>` - Volume (صوت)
`cl` - Clear (مسح القائمة)
`lv` - Leave (خروج)
            """
            await message.channel.send(help_text)
        
        # ========== 1. التشغيل ==========
        elif content.startswith('ش ') or content.startswith('p '):
            query = content[2:].strip()
            if not query:
                await message.channel.send('⚠️ الرجاء كتابة اسم المقطع')
                return
            
            await message.channel.send(f'🔍 جاري البحث عن: **{query}**')
            
            try:
                with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
                    info = ydl.extract_info(query, download=False)
                    if 'entries' in info:
                        url = info['entries'][0]['url']
                        title = info['entries'][0].get('title', query)
                    else:
                        url = info['url']
                        title = info.get('title', query)
                
                voice_client = guild.voice_client
                
                if voice_client and voice_client.channel != message.author.voice.channel:
                    await voice_client.move_to(message.author.voice.channel)
                elif not voice_client:
                    if message.author.voice:
                        voice_client = await message.author.voice.channel.connect()
                    else:
                        await message.channel.send('❌ يجب أن تكون في روم صوتي')
                        return
                
                # إذا كان فيه تشغيل حالي، نضيف للقائمة
                if voice_client.is_playing():
                    self.queue.append({'url': url, 'title': title})
                    await message.channel.send(f'➕ تمت الإضافة إلى القائمة: **{title}**\n📍 الترتيب: {len(self.queue)}')
                else:
                    await self.play_song(guild, url, title)
                    await message.channel.send(f'🎵 **قيد التشغيل:** {title}')
                
            except Exception as e:
                await message.channel.send(f'❌ خطأ: {str(e)[:100]}')
        
        # ========== 2. إيقاف ==========
        elif content in ['وقف', 'stop', 's']:
            voice_client = guild.voice_client
            if voice_client and voice_client.is_playing():
                voice_client.stop()
                await message.channel.send('🛑 تم إيقاف التشغيل')
            else:
                await message.channel.send('⚠️ لا يوجد شيء يتشغل')
        
        # ========== 3. تخطي ==========
        elif content in ['ت', 'skip', 'sk']:
            voice_client = guild.voice_client
            if voice_client and voice_client.is_playing():
                voice_client.stop()
                await message.channel.send('⏭️ تم تخطي المقطع')
            else:
                await message.channel.send('⚠️ لا يوجد شيء يتشغل')
        
        # ========== 4. إيقاف مؤقت ==========
        elif content in ['بـ', 'pause', 'pa']:
            voice_client = guild.voice_client
            if voice_client and voice_client.is_playing():
                voice_client.pause()
                await message.channel.send('⏸️ تم الإيقاف المؤقت')
            else:
                await message.channel.send('⚠️ لا يوجد شيء يتشغل')
        
        # ========== 5. استئناف ==========
        elif content in ['كمل', 'resume', 're']:
            voice_client = guild.voice_client
            if voice_client and voice_client.is_paused():
                voice_client.resume()
                await message.channel.send('▶️ تم استئناف التشغيل')
            else:
                await message.channel.send('⚠️ لا يوجد تشغيل متوقف مؤقتاً')
        
        # ========== 6. تكرار ==========
        elif content in ['كرر', 'loop', 'l']:
            self.song_loop = not self.song_loop
            status = "✅ مفعل" if self.song_loop else "❌ معطل"
            await message.channel.send(f'🔄 وضع التكرار: {status}')
        
        # ========== 7. عرض القائمة ==========
        elif content in ['قائمة', 'queue', 'q']:
            if not self.queue and not self.now_playing:
                await message.channel.send('📭 قائمة التشغيل فارغة')
                return
            
            queue_text = "📜 **قائمة التشغيل:**\n"
            if self.now_playing:
                queue_text += f"🎵 **يتشغل حالياً:** {self.now_playing['title']}\n\n"
            
            if self.queue:
                queue_text += "**المقاطع القادمة:**\n"
                for i, song in enumerate(list(self.queue)[:10], 1):
                    queue_text += f"`{i}`. {song['title'][:50]}\n"
                
                if len(self.queue) > 10:
                    queue_text += f"\n*و {len(self.queue) - 10} مقاطع أخرى...*"
            
            await message.channel.send(queue_text)
        
        # ========== 8. مسح القائمة ==========
        elif content in ['مسح', 'clear', 'cl']:
            self.queue.clear()
            await message.channel.send('🗑️ تم مسح قائمة التشغيل')
        
        # ========== 9. تغيير الصوت ==========
        elif (content.startswith('ص ') or content.startswith('v ')):
            try:
                vol = int(content[2:].strip())
                if 0 <= vol <= 100:
                    self.current_volume = vol / 100.0
                    voice_client = guild.voice_client
                    if voice_client and voice_client.source:
                        voice_client.source.volume = self.current_volume
                    await message.channel.send(f'🔊 تم ضبط الصوت إلى {vol}%')
                else:
                    await message.channel.send('⚠️ الرجاء إدخال رقم بين 0 و 100')
            except:
                await message.channel.send('⚠️ استخدم: `ص 50` أو `v 50`')
        
        # ========== 10. الخروج ==========
        elif content in ['اخرج', 'leave', 'lv']:
            voice_client = guild.voice_client
            if voice_client:
                await voice_client.disconnect()
                self.queue.clear()
                self.now_playing = None
                await message.channel.send('👋 تم الخروج من الروم الصوتي')
            else:
                await message.channel.send('⚠️ لست متصلاً بأي روم')

# تشغيل السكربت
if __name__ == '__main__':
    client = MyClient()
    
    try:
        client.run(TOKEN)
    except Exception as e:
        print(f"❌ خطأ: {e}")