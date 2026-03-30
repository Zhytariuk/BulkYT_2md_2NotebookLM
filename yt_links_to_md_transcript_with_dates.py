import os
import random
import time
import yt_dlp
import re
import sys
import http.cookiejar
import requests

# --- НАЛАШТУВАННЯ ---
input_file = r"D:\G.DRIVE\My_NotebookLM\links_to_process.txt"
output_folder = r"D:\G.DRIVE\My_NotebookLM"
cookie_file = r"D:\G.DRIVE\My_NotebookLM\youtube_cookies.txt"

# --- БЕЗПЕКА (Safe Mode) ---
USE_SAFE_MODE = True  # Емуляція поведінки людини (паузи 12-25с + великі перерви)

def get_yt_session(path):
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://www.youtube.com/',
        'Origin': 'https://www.youtube.com'
    })
    if os.path.exists(path) and os.path.getsize(path) > 0:
        try:
            cj = http.cookiejar.MozillaCookieJar(path)
            cj.load(ignore_discard=True, ignore_expires=True)
            session.cookies = cj
            print(f"[INFO] Куки успішно завантажено: {os.path.basename(path)}")
        except Exception as e:
            print(f"[WARN] Помилка завантаження файлу кук: {e}")
    return session

def natural_sleep(processed_in_session, next_break):
    """Імітація людської поведінки: базові паузи + джиттер + великі рандомні перерви."""
    if not USE_SAFE_MODE:
        time.sleep(random.uniform(2.0, 5.0))
        return next_break

    # 1. Базова пауза з джиттером (імітація перегляду сторінки/читання опису)
    base_delay = random.uniform(12.0, 28.0)
    print(f"      [SLEEP] Пауза: {base_delay:.1f}с (імітація серфінгу)...")
    time.sleep(base_delay)

    # 2. Велика перерва ("відійшов від комп'ютера / інша вкладка")
    if processed_in_session >= next_break:
        big_break = random.uniform(80.0, 240.0)
        print(f"\n      [REST] Велика перерва: імітуємо людську паузу на {big_break/60:.2f} хв...")
        time.sleep(big_break)
        # Вибираємо наступний поріг для перерви (через 3-6 відео)
        return 0, random.randint(3, 6)
    
    return processed_in_session, next_break

def clean_vtt_text(vtt_content):
    """Очищення VTT від таймкодів, службових тегів та повторів."""
    lines = vtt_content.splitlines()
    cleaned_lines = []
    
    content_lines = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith('WEBVTT') or line.startswith('Kind:') or line.startswith('Language:'):
            continue
        if '-->' in line:
            continue
            
        # Видаляємо HTML-подібні теги <c>...</c> або <00:00:00.000>
        line = re.sub(r'<[^>]+>', '', line)
        if line:
            content_lines.append(line)
            
    # Видаляємо послідовні дублікати (особливість YouTube VTT)
    for line in content_lines:
        if not cleaned_lines or line != cleaned_lines[-1]:
            cleaned_lines.append(line)
            
    return " ".join(cleaned_lines)

def fetch_transcript_v2(url, output_folder, cookie_path=None):
    """
    План D: Витягування прямого посилання та самостійне завантаження через requests.
    Це обходить n-challenge та PO-Token перевірки внутрішнього завантажувача yt-dlp.
    """
    try:
        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'cookiefile': cookie_path if cookie_path and os.path.exists(cookie_path) else None,
            # ВИКОРИСТОВУЄМО embedded-клієнт — він найменш захищений від ботів
            'extractor_args': {'youtube': {'player_client': ['web_embedded', 'android']}}
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"      - Отримую посилання на субтитри...")
            info = ydl.extract_info(url, download=False)
            
            # Об'єднуємо авто-субтитри та ручні
            all_subs = info.get('automatic_captions', {})
            all_subs.update(info.get('subtitles', {}))
            
            # Пріоритет мов (uk -> ru -> en)
            target_langs = ['uk', 'ru', 'en']
            target_url = None
            format_ext = 'vtt'
            
            for lang_code in target_langs:
                matching = [k for k in all_subs.keys() if k.startswith(lang_code)]
                if matching:
                    formats = all_subs[matching[0]]
                    # Шукаємо json3 (найпростіший для парсингу) або vtt
                    for f in formats:
                        if f.get('ext') == 'json3':
                            target_url = f.get('url')
                            format_ext = 'json'
                            break
                        if f.get('ext') == 'vtt':
                            target_url = f.get('url')
                            format_ext = 'vtt'
                    if target_url: break
            
            if not target_url:
                # Якщо нічого не підійшло, беремо взагалі будь-яку доступну автоматичну доріжку
                if all_subs:
                    first_lang = list(all_subs.keys())[0]
                    target_url = all_subs[first_lang][0].get('url')
                    format_ext = all_subs[first_lang][0].get('ext', 'vtt')
                    print(f"        [INFO] Мова {target_langs} не знайдена. Беремо {first_lang}.")
                
            if not target_url:
                print(f"        [WARN] Субтитри не знайдені в метаданих.")
                return None
                
            # План F: Додаємо випадкову затримку перед прямим запитом (імітація людської паузи)
            wait_time = random.uniform(5.0, 10.0)
            print(f"      - Очікування {wait_time:.1f}с перед завантаженням ({format_ext})...")
            time.sleep(wait_time)
            
            # Спроба 1: Анонімне завантаження (без кук, іноді це допомагає обійти блок акаунту)
            print(f"      - Спроба анонімного скачування...")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept-Language': 'uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7',
                'Referer': 'https://www.youtube.com/'
            }
            
            try:
                import urllib.request
                req = urllib.request.Request(target_url, headers=headers)
                with urllib.request.urlopen(req, timeout=15) as response:
                    res_content = response.read().decode('utf-8')
                    # Обробляємо текст
                    if format_ext == 'json' or '"events":' in res_content:
                        import json
                        data = json.loads(res_content)
                        text_parts = [s.get('utf8', '').strip() for e in data.get('events', []) for s in e.get('segs', []) if s.get('utf8')]
                        return " ".join(text_parts)
                    return clean_vtt_text(res_content)
            except Exception as e:
                print(f"        [INFO] Анонімний запит не вдався, пробуємо з куками... ({e})")
            
            # Спроба 2: Завантаження з куками (як раніше)
            session = get_yt_session(cookie_path)
            response = session.get(target_url, timeout=20)
            
            if response.status_code == 200:
                res_text = response.text
                if format_ext == 'json' or '"events":' in res_text:
                    import json
                    try:
                        data = json.loads(res_text)
                        text_parts = [s.get('utf8', '').strip() for e in data.get('events', []) for s in e.get('segs', []) if s.get('utf8')]
                        return " ".join(text_parts)
                    except:
                        return clean_vtt_text(res_text)
                return clean_vtt_text(res_text)
            else:
                print(f"        [ERROR] Усі спроби завантаження (анонімно та з куками) відхилені: {response.status_code}")
                
    except Exception as e:
        print(f"        [ERROR] План D не вдався: {e}")
            
    return None

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

def process_youtube_batch(input_txt, output_path):
    urls = load_urls_from_file(input_txt)
    if not urls:
        print("[INFO] Список лінків порожній.")
        return

    print(f"[START] Обробка {len(urls)} відео (включаючи авто-субтитри)...")
    
    session = get_yt_session(cookie_file)
    
    ydl_opts = {
        'quiet': True, 
        'skip_download': True,
        'cookiefile': cookie_file if os.path.exists(cookie_file) else None
    }
    if not os.path.exists(output_path):
        os.makedirs(output_path)

    processed_count = 0
    failed_urls = []
    
    # Змінні для Safe Mode
    session_count = 0 
    next_break_threshold = random.randint(4, 7)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for index, url in enumerate(urls, 1):
            print(f"[{index}/{len(urls)}] Обробка: {url}")
            v_id = get_video_id(url)
            if not v_id:
                print(f"[SKIP] Невірний URL: {url}")
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
                
                print(f"      - Канал: {channel}")
                print(f"      - Назва: {title}")
                text = fetch_transcript_v2(url, output_path, cookie_path=cookie_file)
                
                if text:
                    filename = f"{formatted_date}_ {safe_channel}_ {safe_title}.md"
                    file_full_path = os.path.join(output_path, filename)
                    description = (info.get('description') or '').strip()

                    with open(file_full_path, 'w', encoding='utf-8') as f:
                        # H1 заголовок
                        f.write(f"# {formatted_date}_ {safe_channel}_ {safe_title}\n")
                        f.write("  \n")
                        # YAML front-matter
                        f.write("---\n")
                        f.write("  \n")
                        f.write(f"URL: {url}\n")
                        f.write("tags:   \n")
                        f.write("about:   \n")
                        f.write(f"date: {formatted_date}\n")
                        f.write("  \n")
                        f.write("---\n")
                        f.write("  \n")
                        # TITLE (авто)
                        f.write("**TITLE**:  \n")
                        f.write(f"## {title}\n")
                        f.write("  \n")
                        # URL (авто)
                        f.write("**URL**:  \n")
                        f.write(f"{url}\n")
                        f.write("  \n")
                        # HOOK (вручну)
                        f.write("**HOOK**:  \n")
                        f.write("\n")
                        f.write("  \n")
                        # DESCRIPTION (авто з yt-dlp)
                        f.write("**DESCRIPTION**:  \n")
                        f.write(f"{description}\n" if description else "\n")
                        f.write("  \n")
                        f.write("=====  \n")
                        f.write("  \n")
                        # TIMESTAMPS (вручну)
                        f.write("**TIMESTAMPS**:  \n")
                        f.write("\n")
                        f.write("  \n")
                        f.write("=====  \n")
                        f.write("  \n")
                        # BRIEF/SUMMARY (вручну)
                        f.write("**BRIEF/SUMMARY**:  \n")
                        f.write("##  \n")
                        f.write("\n")
                        f.write("  \n")
                        f.write("=====  \n")
                        f.write("  \n")
                        # TRANSCRIPT (авто)
                        f.write("**TRANSCRIPT**:\n")
                        f.write("\n")
                        f.write(f"{text}\n")
                        f.write("  \n")
                        f.write("=====  \n")
                        f.write("  \n")
                        # BEST COMMENTS (вручну)
                        f.write("**BEST COMMENTS**:\n")
                        f.write("\n")
                        f.write("  \n")
                        f.write("-------------------------------------------\n")
                        f.write("  \n")
                        # TRANSCRIPT WITH TIMESTAMPS (вручну)
                        f.write("**TRANSCRIPT WITH TIMESTAMPS**:  \n")
                        f.write("\n")
                        f.write("  \n")
                        f.write("-------------------------------------------\n")
                        f.write("\n")
                        # ── СУПРОВІДНА СТАТТЯ (вручну) ───────────────────
                        f.write("# \\дата_ [#тег] СУПРОВІДНА СТАТТЯ - тема/\n")
                        f.write("  \n")
                        f.write("**URL**:\n")
                        f.write("\n")
                        f.write("  \n")
                        f.write("**TITLE**:\n")
                        f.write("## \n")
                        f.write("  \n")
                        f.write("**HOOK/TAGS**:\n")
                        f.write("\n")
                        f.write("  \n")
                        f.write("**DESCRIPTION**:\n")
                        f.write("\n")
                        f.write("  \n")
                        f.write("**TEXT**:\n")
                        f.write("\n")
                        f.write("  \n")
                        f.write("##  МІЙ опис суті, МОЇ НОТАТКИ/SUMMARY\n")
                        f.write("\n")
                        f.write("  \n")
                        f.write("-------------------------------------------\n")

                    print(f"      [DONE] Збережено: {filename}")
                    processed_count += 1
                    session_count += 1
                else:
                    print(f"      [ERROR] Субтитри недоступні для: {title}")
                    failed_urls.append(url)
                    session_count += 1 # Навіть при помилці робимо паузи

                session_count, next_break_threshold = natural_sleep(session_count, next_break_threshold)

            except Exception as e:
                print(f"      [CRITICAL] Помилка з {url}: {e}")
                failed_urls.append(url)

    # Оновлюємо файл: залишаємо лише те, що не вдалося обробити
    try:
        if not failed_urls:
            with open(input_txt, 'w', encoding='utf-8') as f:
                f.truncate(0)
            print(f"[INFO] Усі відео оброблено. Файл '{os.path.basename(input_txt)}' очищено.")
        else:
            with open(input_txt, 'w', encoding='utf-8') as f:
                f.write("\n".join(failed_urls) + "\n")
            print(f"[INFO] Обробку завершено. У списку залишилось {len(failed_urls)} посилань.")
    except Exception as e:
        print(f"[WARN] Не вдалося оновити файл списку: {e}")

    print(f"\n--- ПІДСУМОК ---")
    print(f"Успішно оброблено: {processed_count}")
    print(f"Не вдалося: {len(failed_urls)}")

input_file = r"D:\G.DRIVE\My_NotebookLM\links_to_process.txt"
output_folder = r"D:\G.DRIVE\My_NotebookLM"

# --- ЗАПУСК ---
if __name__ == "__main__":
    process_youtube_batch(input_file, output_folder)