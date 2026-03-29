import os
import random
import time
import yt_dlp
import re
import sys
from youtube_transcript_api import (
    YouTubeTranscriptApi,
    NoTranscriptFound,
    IpBlocked,
    RequestBlocked,
)

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", line_buffering=True
    )

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
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
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

def clean_filename(title):
    return re.sub(r'[\\/*?:"<>|]', "", title).strip()

def get_video_id(url):
    if "v=" in url: return url.split("v=")[1].split("&")[0]
    elif "be/" in url: return url.split("be/")[1].split("?")[0]
    return None

def fetch_best_transcript(video_id, session=None):
    """Ручні й авто-субтитри (youtube-transcript-api ≥1.2): uk → ru → en, далі переклад/будь-яка доріжка."""

    def fetched_to_text(fetched):
        full_text = " ".join(s.text.replace("\n", " ") for s in fetched)
        return re.sub(r"\s+", " ", full_text).strip()

    def attempt():
        print(f"      - Спроба отримати субтитри для {video_id}...")
        api = YouTubeTranscriptApi(http_client=session)
        try:
            print("        - Запит fetch(uk, ru, en)...")
            return fetched_to_text(
                api.fetch(video_id, languages=["uk", "ru", "en"])
            )
        except NoTranscriptFound:
            print("        - NoTranscriptFound: перевіряю список доступних...")
            transcript_list = api.list(video_id)
            for t in transcript_list:
                if t.is_translatable:
                    print(f"        - Спроба перекладу {t.language_code} -> uk...")
                    try:
                        return fetched_to_text(t.translate("uk").fetch())
                    except (IpBlocked, RequestBlocked):
                        print("        - Блокування IP під час перекладу.")
                        raise
                    except Exception as e:
                        print(f"        - Помилка під час перекладу: {e}")
                        continue
            for t in transcript_list:
                print(f"        - Спроба завантажити як є: {t.language_code}...")
                try:
                    return fetched_to_text(t.fetch())
                except (IpBlocked, RequestBlocked):
                    print("        - Блокування IP під час завантаження.")
                    raise
                except Exception as e:
                    print(f"        - Помилка під час завантаження: {e}")
                    continue
        except Exception as e:
            if "429" in str(e):
                print("        [CRITICAL] YouTube заблокував запит (Error 429: Too Many Requests).")
                if not (session and session.cookies):
                    print("        [TIP] Спробуйте додати файл youtube_cookies.txt для авторизації.")
            else:
                print(f"        - Помилка API: {e}")
        return None

    for try_i in range(4):
        if try_i:
            delay = 15 * try_i + random.uniform(0, 12)
            print(f"      - ПОВТОР {try_i}/3 після затримки {delay:.1f}с...")
            time.sleep(delay)
        try:
            result = attempt()
        except (IpBlocked, RequestBlocked):
            continue
        return result
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
                text = fetch_best_transcript(v_id, session=session)
                
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