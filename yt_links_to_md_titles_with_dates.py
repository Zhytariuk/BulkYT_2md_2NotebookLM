import os
import random
import time
import yt_dlp
import re
import sys

# --- НАЛАШТУВАННЯ ---
# Ці файли тепер зберігаються у вашій робочій папці окремо від коду
input_file = r"D:\G.DRIVE\My_NotebookLM\links_to_process.txt"
output_folder = r"D:\G.DRIVE\My_NotebookLM"
cookie_file = r"D:\G.DRIVE\My_NotebookLM\youtube_cookies.txt"

# --- БЕЗПЕКА (Safe Mode) ---
# Навіть для метаданих краще робити невеликі паузи
USE_SAFE_MODE = True 

def clean_filename(title):
    return re.sub(r'[\\/*?:"<>|]', "", title).strip()

def get_video_id(url):
    if "v=" in url: return url.split("v=")[1].split("&")[0]
    elif "be/" in url: return url.split("be/")[1].split("?")[0]
    return None

def load_urls_from_file(file_path):
    if not os.path.exists(file_path):
        print(f"[ERROR] Файл зі списком URL не знайдено: {file_path}")
        return []
    with open(file_path, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]

def natural_sleep():
    if USE_SAFE_MODE:
        delay = random.uniform(3.0, 7.0)
        print(f"      [SLEEP] Короткочасна пауза: {delay:.1f}с...")
        time.sleep(delay)

def process_youtube_manual(input_txt, output_path):
    urls = load_urls_from_file(input_txt)
    if not urls:
        print("[INFO] Список лінків порожній.")
        return

    print(f"[START] MANUAL MODE: Створення шаблонів для {len(urls)} відео...")
    
    if not os.path.exists(output_path):
        os.makedirs(output_path)

    ydl_opts = {
        'quiet': True, 
        'skip_download': True,
        'cookiefile': cookie_file if os.path.exists(cookie_file) else None
    }

    processed_count = 0
    failed_urls = []

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for index, url in enumerate(urls, 1):
            print(f"[{index}/{len(urls)}] Метадані: {url}")
            v_id = get_video_id(url)
            if not v_id:
                failed_urls.append(url)
                continue

            try:
                info = ydl.extract_info(url, download=False)
                title = info.get('title', 'Unknown')
                channel = info.get('uploader') or info.get('channel') or 'Unknown Channel'
                raw_date = info.get('upload_date', '00000000')
                formatted_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"
                
                safe_title = clean_filename(title)
                safe_channel = clean_filename(channel)
                
                filename = f"{formatted_date}_ {safe_channel}_ {safe_title}.md"
                file_full_path = os.path.join(output_path, filename)
                description = (info.get('description') or '').strip()

                # Шаблон з плейсхолдером замість транскрипту
                with open(file_full_path, 'w', encoding='utf-8') as f:
                    f.write(f"# {formatted_date}_ {safe_channel}_ {safe_title}\n\n")
                    f.write("---\n\n")
                    f.write(f"URL: {url}\ndate: {formatted_date}\n\n---\n\n")
                    f.write(f"**TITLE**:  \n## {title}\n\n")
                    f.write(f"**URL**:  \n{url}\n\n")
                    f.write("**DESCRIPTION**:  \n")
                    f.write(f"{description}\n\n" if description else "\n\n")
                    f.write("=====  \n\n**TRANSCRIPT**:\n\n")
                    f.write("> [!IMPORTANT]\n")
                    f.write("> ТРАНСКРИПТ НЕ ВИКАЧАНО АВТОМАТИЧНО.\n")
                    f.write("> Скопіюйте текст із YouTube вручну та вставте сюди.\n\n")
                    f.write("-------------------------------------------\n")

                print(f"      [DONE] Шаблон створено: {filename}")
                processed_count += 1
                natural_sleep()

            except Exception as e:
                print(f"      [ERROR] Помилка: {e}")
                failed_urls.append(url)

    # Оновлюємо список
    if not failed_urls:
        with open(input_txt, 'w', encoding='utf-8') as f: f.truncate(0)
    else:
        with open(input_txt, 'w', encoding='utf-8') as f:
            f.write("\n".join(failed_urls) + "\n")

    print(f"\n--- ПІДСУМОК (Manual Mode) ---")
    print(f"Шаблонів створено: {processed_count}")
    print(f"Не вдалося: {len(failed_urls)}")

if __name__ == "__main__":
    process_youtube_manual(input_file, output_folder)
