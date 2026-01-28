#!/usr/bin/env python3
"""
Python Obfuscator Telegram Bot
Fitur: Upload file .py -> Terima file terobfuscate
Dengan sistem auto-update dan logging
"""

import os
import sys
import logging
import asyncio
import json
import hashlib
import tempfile
import shutil
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple

# Telegram Bot
from telegram import Update, Bot, InputFile
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    filters, 
    ContextTypes,
    CallbackContext
)

# Import obfuscator modules
from obfuscator_core import PythonObfuscator, FileObfuscator, AdvancedObfuscator
from update_system import UpdateSystem

# ============================================================================
# Konfigurasi
# ============================================================================

class Config:
    """Konfigurasi bot"""
    # Token bot (GANTI DENGAN TOKEN ANDA)
    BOT_TOKEN = "8504446249:AAEdqWr0a1agNSw4j5pEFVZQnLqeM5nYoos"
    
    # Admin user IDs (untuk akses khusus)
    ADMIN_IDS = [8295141776]  # ID Telegram Anda
    
    # Update channel untuk notifikasi
    UPDATE_CHANNEL = "@TrafashiNight"
    
    # Path untuk file
    UPLOAD_FOLDER = "uploads"
    OUTPUT_FOLDER = "outputs"
    LOG_FOLDER = "logs"
    
    # Batasan file
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS = {'.py'}
    
    # Rate limiting
    REQUESTS_PER_MINUTE = 5
    USER_COOLDOWN = 30  # detik
    
    @classmethod
    def init_folders(cls):
        """Buat folder yang diperlukan"""
        folders = [cls.UPLOAD_FOLDER, cls.OUTPUT_FOLDER, cls.LOG_FOLDER]
        for folder in folders:
            os.makedirs(folder, exist_ok=True)

# ============================================================================
# Setup Logging
# ============================================================================

def setup_logging():
    """Setup logging yang komprehensif"""
    log_filename = f"{Config.LOG_FOLDER}/bot_{datetime.now().strftime('%Y%m%d')}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Kurangi log level untuk beberapa library
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('telegram').setLevel(logging.WARNING)
    
    return logging.getLogger(__name__)

logger = setup_logging()

# ============================================================================
# User Management & Rate Limiting
# ============================================================================

class UserManager:
    """Manajemen user dan rate limiting"""
    
    def __init__(self):
        self.user_requests: Dict[int, List[datetime]] = {}
        self.user_files: Dict[int, Dict] = {}
        self.cooldown_users: Dict[int, datetime] = {}
    
    def can_make_request(self, user_id: int) -> Tuple[bool, str]:
        """Cek apakah user bisa membuat request"""
        now = datetime.now()
        
        # Cek cooldown
        if user_id in self.cooldown_users:
            cooldown_end = self.cooldown_users[user_id]
            if now < cooldown_end:
                remaining = (cooldown_end - now).seconds
                return False, f"Silakan tunggu {remaining} detik sebelum request lagi"
        
        # Rate limiting per menit
        if user_id in self.user_requests:
            user_reqs = self.user_requests[user_id]
            # Hapus request lebih dari 1 menit yang lalu
            user_reqs = [req for req in user_reqs if (now - req).seconds < 60]
            self.user_requests[user_id] = user_reqs
            
            if len(user_reqs) >= Config.REQUESTS_PER_MINUTE:
                self.cooldown_users[user_id] = now + timedelta(seconds=Config.USER_COOLDOWN)
                return False, f"Rate limit tercapai. Tunggu {Config.USER_COOLDOWN} detik"
        
        return True, ""
    
    def add_request(self, user_id: int):
        """Tambahkan request user"""
        if user_id not in self.user_requests:
            self.user_requests[user_id] = []
        self.user_requests[user_id].append(datetime.now())
    
    def track_file(self, user_id: int, file_info: Dict):
        """Track file yang diupload user"""
        if user_id not in self.user_files:
            self.user_files[user_id] = {}
        
        file_hash = file_info.get('hash', 'unknown')
        self.user_files[user_id][file_hash] = {
            **file_info,
            'timestamp': datetime.now()
        }
    
    def get_user_stats(self, user_id: int) -> Dict:
        """Dapatkan statistik user"""
        stats = {
            'total_requests': 0,
            'files_processed': 0,
            'last_request': None
        }
        
        if user_id in self.user_requests:
            stats['total_requests'] = len(self.user_requests[user_id])
            if self.user_requests[user_id]:
                stats['last_request'] = self.user_requests[user_id][-1]
        
        if user_id in self.user_files:
            stats['files_processed'] = len(self.user_files[user_id])
        
        return stats

user_manager = UserManager()

# ============================================================================
# File Processing
# ============================================================================

class FileProcessor:
    """Processor untuk file Python"""
    
    def __init__(self):
        self.obfuscator = FileObfuscator()
        self.advanced_obf = AdvancedObfuscator()
        self.file_hashes: Dict[str, Dict] = {}
    
    def calculate_file_hash(self, file_path: str) -> str:
        """Hitung hash SHA256 dari file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def validate_file(self, file_path: str) -> Tuple[bool, str]:
        """Validasi file Python"""
        try:
            # Cek ukuran
            file_size = os.path.getsize(file_path)
            if file_size > Config.MAX_FILE_SIZE:
                return False, f"File terlalu besar ({file_size} bytes). Maks: {Config.MAX_FILE_SIZE} bytes"
            
            # Cek ekstensi
            if not file_path.lower().endswith('.py'):
                return False, "Hanya file .py yang diperbolehkan"
            
            # Cek apakah valid Python
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Coba compile untuk validasi sintaks
            compile(content, file_path, 'exec')
            
            # Cek untuk kode berbahaya
            dangerous_patterns = [
                'import os.system',
                'import subprocess',
                'eval(',
                'exec(',
                '__import__',
                'open(',
                'compile('
            ]
            
            for pattern in dangerous_patterns:
                if pattern in content:
                    logger.warning(f"Potensi kode berbahaya: {pattern}")
                    # Tidak langsung ditolak, tapi dicatat
            
            return True, "File valid"
            
        except SyntaxError as e:
            return False, f"Error sintaks Python: {str(e)}"
        except Exception as e:
            return False, f"Error validasi: {str(e)}"
    
    def process_file(self, file_path: str, user_id: int, level: int = 2, 
                    advanced: bool = False) -> Tuple[Optional[str], str]:
        """Process file untuk obfuscation"""
        try:
            # Validasi file
            is_valid, message = self.validate_file(file_path)
            if not is_valid:
                return None, message
            
            # Hitung hash
            file_hash = self.calculate_file_hash(file_path)
            
            # Cek cache (jangan proses file yang sama berulang)
            cache_key = f"{file_hash}_{level}_{advanced}"
            if cache_key in self.file_hashes:
                cached = self.file_hashes[cache_key]
                if os.path.exists(cached['output_path']):
                    logger.info(f"Cache hit untuk file {file_hash}")
                    return cached['output_path'], "Berhasil (dari cache)"
            
            # Baca file
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()
            
            # Generate nama output
            original_name = os.path.basename(file_path)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_name = f"obf_{user_id}_{timestamp}_{original_name}"
            output_path = os.path.join(Config.OUTPUT_FOLDER, output_name)
            
            # Proses obfuscation
            logger.info(f"Processing file {original_name} untuk user {user_id}, level {level}")
            
            if advanced:
                # Advanced multi-layer obfuscation
                obfuscated_code = self.advanced_obf.multi_layer_obfuscate(code, layers=3)
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(obfuscated_code)
            else:
                # Standard obfuscation
                self.obfuscator.obfuscate_file(
                    file_path, 
                    output_path, 
                    level=level
                )
            
            # Simpan ke cache
            self.file_hashes[cache_key] = {
                'original_path': file_path,
                'output_path': output_path,
                'user_id': user_id,
                'timestamp': datetime.now(),
                'hash': file_hash
            }
            
            return output_path, "Obfuscation berhasil"
            
        except Exception as e:
            logger.error(f"Error processing file: {e}", exc_info=True)
            return None, f"Error processing: {str(e)}"
    
    def cleanup_old_files(self, max_age_hours: int = 24):
        """Bersihkan file lama"""
        try:
            now = datetime.now()
            folders = [Config.UPLOAD_FOLDER, Config.OUTPUT_FOLDER]
            
            for folder in folders:
                if not os.path.exists(folder):
                    continue
                    
                for filename in os.listdir(folder):
                    file_path = os.path.join(folder, filename)
                    try:
                        file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                        age_hours = (now - file_time).total_seconds() / 3600
                        
                        if age_hours > max_age_hours:
                            os.remove(file_path)
                            logger.info(f"Cleaned up old file: {file_path}")
                    except Exception as e:
                        logger.warning(f"Error cleaning file {file_path}: {e}")
            
            # Juga bersihkan cache lama
            old_cache_keys = []
            for key, info in self.file_hashes.items():
                if (now - info['timestamp']).total_seconds() > max_age_hours * 3600:
                    old_cache_keys.append(key)
            
            for key in old_cache_keys:
                del self.file_hashes[key]
                
        except Exception as e:
            logger.error(f"Error in cleanup: {e}")

file_processor = FileProcessor()

# ============================================================================
# Telegram Bot Handlers
# ============================================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk /start"""
    user = update.effective_user
    user_id = user.id
    
    welcome_message = f"""
🤖 **Python Obfuscator Bot**

Halo {user.first_name}! Saya bot untuk obfuscate file Python.

**Cara Pakai:**
1. Kirim file `.py` ke saya
2. Pilih level obfuscation
3. Terima file hasil obfuscation

**Commands:**
/start - Tampilkan pesan ini
/help - Bantuan lengkap
/obfuscate - Obfuscate file
/stats - Statistik penggunaan
/level [1-3] - Set obfuscation level
/advanced - Mode advanced obfuscation
/admin - Menu admin (admin only)

**Level Obfuscation:**
1️⃣ **Low** - Rename variabel dasar
2️⃣ **Medium** - + String encoding (default)
3️⃣ **High** - + Bytecode compilation

**Note:** File akan otomatis dihapus setelah 24 jam.
"""
    
    await update.message.reply_text(welcome_message, parse_mode='Markdown')
    
    # Track user
    user_manager.add_request(user_id)
    logger.info(f"User {user_id} ({user.username}) started bot")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk /help"""
    help_text = """
📚 **Bantuan Python Obfuscator Bot**

**Fitur:**
• Obfuscate file Python (.py)
• 3 level obfuscation
• Advanced multi-layer obfuscation
• Auto-cleanup file lama
• Rate limiting

**Cara Obfuscate:**
1. Kirim file `.py` ke bot
2. Bot akan tanya level obfuscation
3. Pilih level (1-3) atau /advanced
4. Tunggu proses selesai
5. Download file hasil

**Commands:**
/start - Memulai bot
/help - Bantuan ini
/obfuscate - Mulai obfuscation
/stats - Lihat statistik anda
/level [1-3] - Set level default
/advanced - Mode advanced
/settings - Pengaturan
/cancel - Batalkan proses

**Tips:**
• File maksimal 10MB
• Backup file original terlebih dahulu
• Test file hasil sebelum digunakan
• Gunakan /advanced untuk proteksi ekstra

**Support:** @TrafashiNight
"""
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def obfuscate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk /obfuscate"""
    user_id = update.effective_user.id
    
    # Cek rate limiting
    can_request, message = user_manager.can_make_request(user_id)
    if not can_request:
        await update.message.reply_text(f"⏳ {message}")
        return
    
    # Tambahkan request
    user_manager.add_request(user_id)
    
    # Simpan state untuk user
    context.user_data['awaiting_file'] = True
    context.user_data['obf_level'] = 2  # Default level
    
    await update.message.reply_text(
        "📁 **Kirim file Python (.py) yang ingin diobfuscate**\n\n"
        "Anda bisa reply pesan ini dengan file .py\n"
        "Atau gunakan /cancel untuk membatalkan",
        parse_mode='Markdown'
    )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk file document"""
    user = update.effective_user
    user_id = user.id
    
    # Cek apakah user sedang menunggu file
    if not context.user_data.get('awaiting_file', False):
        await update.message.reply_text(
            "Gunakan /obfuscate terlebih dahulu untuk memulai proses."
        )
        return
    
    # Cek rate limiting
    can_request, message = user_manager.can_make_request(user_id)
    if not can_request:
        await update.message.reply_text(f"⏳ {message}")
        context.user_data['awaiting_file'] = False
        return
    
    document = update.message.document
    
    # Validasi file
    if not document.file_name.endswith('.py'):
        await update.message.reply_text(
            "❌ Hanya file .py yang didukung!\n"
            "Silakan kirim file dengan ekstensi .py"
        )
        context.user_data['awaiting_file'] = False
        return
    
    # Cek ukuran file
    if document.file_size > Config.MAX_FILE_SIZE:
        await update.message.reply_text(
            f"❌ File terlalu besar!\n"
            f"Maksimal: {Config.MAX_FILE_SIZE // 1024 // 1024}MB\n"
            f"Ukuran anda: {document.file_size // 1024 // 1024}MB"
        )
        context.user_data['awaiting_file'] = False
        return
    
    # Konfirmasi dan tanya level
    context.user_data['file_info'] = {
        'file_id': document.file_id,
        'file_name': document.file_name,
        'file_size': document.file_size
    }
    
    # Reset awaiting file state
    context.user_data['awaiting_file'] = False
    
    # Kirim menu level
    keyboard = [
        ["Level 1 (Low)", "Level 2 (Medium)", "Level 3 (High)"],
        ["Advanced Mode", "Cancel"]
    ]
    
    await update.message.reply_text(
        f"📄 **File Diterima:** {document.file_name}\n"
        f"📦 **Size:** {document.file_size // 1024} KB\n\n"
        "**Pilih Level Obfuscation:**\n"
        "• Level 1: Rename variabel dasar\n"
        "• Level 2: + String encoding (rekomendasi)\n"
        "• Level 3: + Bytecode compilation\n"
        "• Advanced: Multi-layer protection\n\n"
        "Klik pilihan di bawah atau gunakan /level [1-3]",
        reply_markup={
            'keyboard': keyboard,
            'resize_keyboard': True,
            'one_time_keyboard': True
        }
    )

async def handle_level_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk pemilihan level"""
    user_id = update.effective_user.id
    text = update.message.text
    
    if 'file_info' not in context.user_data:
        await update.message.reply_text(
            "Silakan upload file terlebih dahulu dengan /obfuscate"
        )
        return
    
    file_info = context.user_data['file_info']
    
    # Tentukan level berdasarkan teks
    level_map = {
        "Level 1 (Low)": 1,
        "Level 2 (Medium)": 2,
        "Level 3 (High)": 3,
        "Advanced Mode": "advanced"
    }
    
    if text not in level_map and text.lower() != 'cancel':
        await update.message.reply_text("Pilihan tidak valid!")
        return
    
    if text.lower() == 'cancel':
        await update.message.reply_text("❌ Proses dibatalkan.")
        context.user_data.clear()
        return
    
    # Download dan proses file
    await update.message.reply_text("⏳ **Mendownload file...**")
    
    try:
        # Download file dari Telegram
        bot = context.bot
        file = await bot.get_file(file_info['file_id'])
        
        # Buat temp file
        temp_dir = tempfile.mkdtemp()
        download_path = os.path.join(temp_dir, file_info['file_name'])
        
        await file.download_to_drive(download_path)
        
        await update.message.reply_text("✅ **File berhasil didownload!**\n⏳ **Memproses obfuscation...**")
        
        # Proses file
        if text == "Advanced Mode":
            output_path, message = file_processor.process_file(
                download_path, user_id, advanced=True
            )
            process_type = "Advanced Obfuscation"
        else:
            level = level_map[text]
            output_path, message = file_processor.process_file(
                download_path, user_id, level=level
            )
            process_type = f"Level {level} Obfuscation"
        
        if output_path:
            # Kirim file hasil
            with open(output_path, 'rb') as f:
                await update.message.reply_document(
                    document=InputFile(f, filename=f"obf_{file_info['file_name']}"),
                    caption=f"✅ **{process_type} Selesai!**\n"
                           f"📄 Original: {file_info['file_name']}\n"
                           f"🔄 Method: {process_type}\n"
                           f"👤 User: @{update.effective_user.username or 'N/A'}\n"
                           f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                           f"**Note:** File akan otomatis dihapus setelah 24 jam.",
                    parse_mode='Markdown'
                )
            
            # Track file
            user_manager.track_file(user_id, {
                'original_name': file_info['file_name'],
                'output_name': os.path.basename(output_path),
                'level': level_map.get(text, 'advanced'),
                'timestamp': datetime.now()
            })
            
            logger.info(f"Successfully processed file for user {user_id}: {file_info['file_name']}")
        else:
            await update.message.reply_text(f"❌ **Error:** {message}")
        
        # Cleanup temp files
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        # Reset user data
        context.user_data.clear()
        
    except Exception as e:
        logger.error(f"Error processing for user {user_id}: {e}", exc_info=True)
        await update.message.reply_text(f"❌ **Error:** {str(e)}")
        
        # Cleanup
        if 'temp_dir' in locals():
            shutil.rmtree(temp_dir, ignore_errors=True)
        context.user_data.clear()

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk /stats"""
    user_id = update.effective_user.id
    stats = user_manager.get_user_stats(user_id)
    
    stats_text = f"""
📊 **Statistik Penggunaan**

👤 **User:** @{update.effective_user.username or 'N/A'}
🆔 **ID:** `{user_id}`

📈 **Aktivitas:**
• Total Requests: {stats['total_requests']}
• File Diproses: {stats['files_processed']}
• Request Terakhir: {stats['last_request'].strftime('%Y-%m-%d %H:%M') if stats['last_request'] else 'N/A'}

⚙️ **Pengaturan:**
• Level Default: {context.user_data.get('obf_level', 2)}
• Mode Advanced: {'Aktif' if context.user_data.get('advanced_mode', False) else 'Nonaktif'}

💾 **Storage:**
• Upload Folder: {len(os.listdir(Config.UPLOAD_FOLDER)) if os.path.exists(Config.UPLOAD_FOLDER) else 0} files
• Output Folder: {len(os.listdir(Config.OUTPUT_FOLDER)) if os.path.exists(Config.OUTPUT_FOLDER) else 0} files

🔄 **Auto-cleanup:** Setiap 24 jam
"""
    
    await update.message.reply_text(stats_text, parse_mode='Markdown')

async def level_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk /level"""
    args = context.args
    
    if not args or len(args) != 1:
        await update.message.reply_text(
            "Gunakan: /level [1-3]\n"
            "1: Low (rename variabel)\n"
            "2: Medium (default)\n"
            "3: High (bytecode)"
        )
        return
    
    try:
        level = int(args[0])
        if level not in [1, 2, 3]:
            raise ValueError
        
        context.user_data['obf_level'] = level
        await update.message.reply_text(f"✅ Level obfuscation diatur ke: **Level {level}**", parse_mode='Markdown')
        
    except ValueError:
        await update.message.reply_text("Level harus 1, 2, atau 3!")

async def advanced_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk /advanced"""
    context.user_data['advanced_mode'] = True
    await update.message.reply_text(
        "🔒 **Advanced Mode Diaktifkan!**\n\n"
        "Mode ini menggunakan multi-layer obfuscation:\n"
        "• XOR encryption\n"
        "• Zlib compression\n"
        "• Base64 encoding\n"
        "• Multiple layers\n\n"
        "File akan lebih aman tapi ukuran mungkin bertambah.\n"
        "Kirim file dengan /obfuscate untuk memulai."
    )

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk /admin (admin only)"""
    user_id = update.effective_user.id
    
    if user_id not in Config.ADMIN_IDS:
        await update.message.reply_text("❌ Akses ditolak!")
        return
    
    # Admin panel
    admin_text = f"""
👑 **Admin Panel**

📊 **System Stats:**
• Total Users: {len(user_manager.user_requests)}
• Active Today: {sum(1 for reqs in user_manager.user_requests.values() if reqs and (datetime.now() - reqs[-1]).seconds < 86400)}
• Files in Cache: {len(file_processor.file_hashes)}

💾 **Storage:**
• Uploads: {sum(os.path.getsize(os.path.join(Config.UPLOAD_FOLDER, f)) for f in os.listdir(Config.UPLOAD_FOLDER) if os.path.isfile(os.path.join(Config.UPLOAD_FOLDER, f))) // 1024} KB
• Outputs: {sum(os.path.getsize(os.path.join(Config.OUTPUT_FOLDER, f)) for f in os.listdir(Config.OUTPUT_FOLDER) if os.path.isfile(os.path.join(Config.OUTPUT_FOLDER, f))) // 1024} KB

⚙️ **Commands:**
/cleanup - Bersihkan file lama
/broadcast - Broadcast message
/userinfo [id] - Info user
/system - System info
/update - Check update
"""
    
    await update.message.reply_text(admin_text, parse_mode='Markdown')

async def cleanup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cleanup files (admin only)"""
    user_id = update.effective_user.id
    
    if user_id not in Config.ADMIN_IDS:
        await update.message.reply_text("❌ Akses ditolak!")
        return
    
    await update.message.reply_text("🧹 **Membersihkan file lama...**")
    
    try:
        file_processor.cleanup_old_files()
        
        # Juga bersihkan folder
        for folder in [Config.UPLOAD_FOLDER, Config.OUTPUT_FOLDER]:
            if os.path.exists(folder):
                for f in os.listdir(folder):
                    file_path = os.path.join(folder, f)
                    try:
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                    except:
                        pass
        
        await update.message.reply_text("✅ **Cleanup selesai!**")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk /cancel"""
    context.user_data.clear()
    await update.message.reply_text("✅ Semua proses dibatalkan.")

async def error_handler(update: Update, context: CallbackContext):
    """Handler untuk error"""
    logger.error(f"Update {update} caused error {context.error}", exc_info=True)
    
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ Terjadi error! Silakan coba lagi nanti."
            )
    except:
        pass

# ============================================================================
# Auto-cleanup Task
# ============================================================================

async def auto_cleanup_task(context: CallbackContext):
    """Task untuk auto-cleanup file"""
    logger.info("Running auto-cleanup task...")
    file_processor.cleanup_old_files()

async def status_monitor_task(context: CallbackContext):
    """Task untuk monitor status"""
    total_users = len(user_manager.user_requests)
    cache_size = len(file_processor.file_hashes)
    
    logger.info(f"Status Monitor - Users: {total_users}, Cache: {cache_size}")

# ============================================================================
# Main Function
# ============================================================================

def main():
    """Main function untuk menjalankan bot"""
    # Inisialisasi folder
    Config.init_folders()
    
    # Setup update system
    update_system = UpdateSystem()
    
    # Cek update
    logger.info("Checking for updates...")
    update_available, update_info = update_system.check_update()
    
    if update_available:
        logger.info(f"Update available: {update_info['version']}")
        # Update bisa dilakukan otomatis atau manual
    
    # Buat application
    app = Application.builder().token(Config.BOT_TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("obfuscate", obfuscate_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("level", level_command))
    app.add_handler(CommandHandler("advanced", advanced_command))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("cleanup", cleanup_command))
    app.add_handler(CommandHandler("cancel", cancel_command))
    
    # Message handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_level_selection))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    
    # Error handler
    app.add_error_handler(error_handler)
    
    # Setup jobs
    job_queue = app.job_queue
    
    if job_queue:
        # Auto-cleanup setiap 6 jam
        job_queue.run_repeating(auto_cleanup_task, interval=6*3600, first=10)
        
        # Status monitor setiap jam
        job_queue.run_repeating(status_monitor_task, interval=3600, first=30)
    
    # Start bot
    logger.info("Bot starting...")
    print("=" * 60)
    print("PYTHON OBFUSCATOR TELEGRAM BOT")
    print("=" * 60)
    print(f"Bot Token: {Config.BOT_TOKEN[:10]}...")
    print(f"Admin IDs: {Config.ADMIN_IDS}")
    print(f"Upload Folder: {Config.UPLOAD_FOLDER}")
    print(f"Output Folder: {Config.OUTPUT_FOLDER}")
    print("=" * 60)
    print("Bot is running. Press Ctrl+C to stop.")
    
    # Jalankan bot
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        print("\nBot stopped.")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"Fatal error: {e}")
