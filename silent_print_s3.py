import time
import os
import sys
import json
import win32con
import win32print
import win32ui
import win32gui
from PIL import Image, ImageWin, ImageDraw, ImageFont
import boto3
from botocore.exceptions import ClientError
import tempfile
import datetime

WINDOWS_PRINT_AVAILABLE = True
S3_BUCKET_NAME = 'wikilect-ecom-expo-may-2025' 
CHECK_INTERVAL_SECONDS = 1  # Проверка каждую секунду
TXT_EXTENSION = '.txt'  # Расширение для текстовых файлов
TEMPLATE_IMAGE = 'src\A5-front.png'  # Путь к шаблону изображения
PRINTED_LOG_FILE = 'printed_files.txt'  # Файл для хранения истории печати

def get_s3_client():
    """Создает и возвращает клиент S3 для Yandex Cloud."""
    try:
        # Создаем клиент для Yandex Cloud S3
        return boto3.client(
            's3',
            endpoint_url='https://storage.yandexcloud.net',
            region_name='ru-central1'
        )
    except Exception as e:
        print(f"Ошибка при создании S3 клиента: {e}")
        return None

def load_printed_files():
    """Загружает список уже напечатанных файлов из лог-файла."""
    printed_files = set()
    if os.path.exists(PRINTED_LOG_FILE):
        try:
            with open(PRINTED_LOG_FILE, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        parts = line.split(',', 1)
                        if len(parts) == 2:
                            file_key, _ = parts
                            printed_files.add(file_key)
        except Exception as e:
            print(f"Ошибка при чтении лог-файла: {e}")
    return printed_files

def save_printed_file(file_key):
    """Сохраняет информацию о напечатанном файле в лог."""
    try:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(PRINTED_LOG_FILE, 'a') as f:
            f.write(f"{file_key},{timestamp}\n")
        return True
    except Exception as e:
        print(f"Ошибка при записи в лог-файл: {e}")
        return False

def list_files_in_s3_bucket(s3_client, bucket_name):
    """Возвращает множество ключей файлов в указанном S3 бакете с их временем последнего изменения."""
    file_info = {}
    if s3_client is None:
        print("S3 клиент не инициализирован.")
        return file_info
    try:
        response = s3_client.list_objects_v2(Bucket=bucket_name)
        if 'Contents' in response:
            for obj in response['Contents']:
                key = obj['Key']
                last_modified = obj['LastModified']
                file_info[key] = last_modified
    except ClientError as e:
        print(f"Ошибка при получении списка файлов из S3: {e}")
    return file_info

def download_file_from_s3(s3_client, bucket_name, file_key):
    """Скачивает файл из S3 и возвращает путь к временному файлу."""
    if s3_client is None:
        print("S3 клиент не инициализирован.")
        return None
    try:
        # Создаем временный файл с правильным расширением
        _, ext = os.path.splitext(file_key)
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
        temp_file.close()
        
        # Скачиваем файл из S3
        s3_client.download_file(bucket_name, file_key, temp_file.name)
        return temp_file.name
    except ClientError as e:
        print(f"Ошибка при скачивании файла из S3: {e}")
        return None
    except Exception as e:
        print(f"Непредвиденная ошибка при скачивании файла: {e}")
        return None

def read_text_from_file(file_path):
    """Читает текст из файла."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        # Если UTF-8 не работает, пробуем другие кодировки
        try:
            with open(file_path, 'r', encoding='cp1251') as f:
                return f.read()
        except Exception as e:
            print(f"Ошибка при чтении файла с кодировкой cp1251: {e}")
            return None
    except Exception as e:
        print(f"Ошибка при чтении файла: {e}")
        return None

def create_image_with_text(template_path, text_content):
    """Создает изображение с текстом на основе шаблона с улучшенной поддержкой эмодзи."""
    try:
        # Открываем шаблон изображения
        img = Image.open(template_path)
        draw = ImageDraw.Draw(img)
        
        # Используем шрифты Noto Sans и Noto Color Emoji для поддержки кириллицы и эмодзи
        try:
            # Используем указанный пользователем шрифт Noto Sans для основного текста
            custom_font_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src', 'font', 'NotoSans-Regular.ttf')
            
            # Проверяем наличие шрифтов для эмодзи
            font_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src', 'font')
            emoji_font_candidates = [
                os.path.join(font_dir, 'NotoColorEmoji-Regular.ttf'),  # Основной шрифт для эмодзи
                os.path.join(font_dir, 'NotoEmoji-Regular.ttf'),       # Альтернативный шрифт для эмодзи
                os.path.join(os.environ['WINDIR'], 'Fonts', 'seguiemj.ttf')  # Windows Segoe UI Emoji
            ]
            
            # Проверяем наличие шрифтов для эмодзи
            emoji_font_path = None
            for candidate in emoji_font_candidates:
                if os.path.exists(candidate):
                    emoji_font_path = candidate
                    emoji_font_exists = True
                    print(f"Найден шрифт для эмодзи: {emoji_font_path}")
                    break
            else:
                emoji_font_exists = False
            
            if os.path.exists(custom_font_path):
                # Используем шрифт Noto Sans для основного текста
                font = ImageFont.truetype(custom_font_path, 24)
                print(f"Используется шрифт Noto Sans: {custom_font_path}")
                
                # Если доступен шрифт для эмодзи, загрузим его
                if emoji_font_exists:
                    try:
                        # Используем увеличенный размер для лучшего отображения эмодзи
                        try:
                            # Загружаем шрифт с embedded_color=True для поддержки цветных эмодзи
                            emoji_font = ImageFont.truetype(emoji_font_path, 36, layout_engine=ImageFont.LAYOUT_RAQM, embedded_color=True)
                        except (TypeError, AttributeError):
                            try:
                                # Пробуем без layout_engine
                                emoji_font = ImageFont.truetype(emoji_font_path, 36, embedded_color=True)
                            except (TypeError, AttributeError):
                                # Если embedded_color не поддерживается
                                emoji_font = ImageFont.truetype(emoji_font_path, 36)
                        emoji_name = os.path.basename(emoji_font_path)
                        print(f"Используется шрифт {emoji_name} для эмодзи: {emoji_font_path}")
                    except Exception as e:
                        print(f"Ошибка при загрузке шрифта для эмодзи: {e}")
                        emoji_font = None
                else:
                    emoji_font = None
                    print("Не найден подходящий шрифт для эмодзи, эмодзи могут отображаться некорректно")
            else:
                # Если шрифт не найден, используем резервные шрифты
                print(f"Шрифт не найден по пути: {custom_font_path}")
                print("Используем резервные шрифты...")
                
                # Резервные шрифты с хорошей поддержкой кириллицы и эмодзи
                font_candidates = [
                    'seguiemj.ttf',  # Segoe UI Emoji (отличная поддержка эмодзи)
                    'seguisym.ttf',  # Segoe UI Symbol (хорошая поддержка эмодзи и кириллицы)
                    'segoeui.ttf',   # Segoe UI (хорошая поддержка кириллицы)
                ]
                
                font_path = None
                for font_name in font_candidates:
                    candidate_path = os.path.join(os.environ['WINDIR'], 'Fonts', font_name)
                    if os.path.exists(candidate_path):
                        font_path = candidate_path
                        break
                
                if font_path:
                    font = ImageFont.truetype(font_path, 24)
                    print(f"Используется резервный шрифт: {font_path}")
                else:
                    # Если ни один шрифт не найден, используем стандартный
                    raise Exception("Не найден подходящий шрифт")
        except Exception as e:
            print(f"Ошибка при загрузке шрифта: {e}, пробуем запасной вариант")
            try:
                # Пробуем использовать Arial, который точно поддерживает кириллицу
                arial_path = os.path.join(os.environ['WINDIR'], 'Fonts', 'arial.ttf')
                if os.path.exists(arial_path):
                    font = ImageFont.truetype(arial_path, 24)
                    print(f"Используется запасной шрифт: {arial_path}")
                else:
                    # Если Arial не найден, используем стандартный шрифт
                    font = ImageFont.load_default()
                    print("Используется стандартный шрифт (может не поддерживать кириллицу)")
            except Exception as e2:
                print(f"Ошибка при загрузке запасного шрифта: {e2}, используем стандартный шрифт")
                font = ImageFont.load_default()
        
        text_x = 52  # Левая граница
        text_y = 140  # Верхняя граница
        text_width = 776 - 52  # Ширина текстовой области
        text_height = 960 - 140  # Высота текстовой области
        
        # Преобразуем текст для правильного отображения эмодзи с использованием разных вариантов синтаксиса
        try:
            original_text = text_content
            processed_text = text_content
            emojized = False
            
            # Пробуем с разными вариантами синтаксиса для эмодзи
            try:
                processed_text = emoji.emojize(text_content, language='alias')
                if processed_text != text_content:
                    text_content = processed_text
                    emojized = True
                    print("Эмодзи успешно преобразованы с помощью alias (:smile:)")
            except Exception as e:
                print(f"Ошибка при преобразовании эмодзи с alias: {e}")
            
            # 2. Со стандартным языком (длинные коды: :grinning_face:)
            try:
                processed_text = emoji.emojize(text_content)
                if processed_text != text_content:
                    text_content = processed_text
                    emojized = True
                    print("Эмодзи успешно преобразованы со стандартными кодами (:grinning_face:)")
            except Exception as e:
                print(f"Ошибка при преобразовании эмодзи со стандартными кодами: {e}")
            
            # 3. Пробуем все варианты синтаксиса сразу
            try:
                if not emojized:
                    # Использование варианта со всеми доступными вариантами синтаксиса
                    processed_text = emoji.emojize(text_content, variant="emoji_type", language="alias")
                    if processed_text != text_content:
                        text_content = processed_text
                        emojized = True
                        print("Эмодзи успешно преобразованы с использованием emoji_type")
            except Exception as e:
                print(f"Ошибка при преобразовании эмодзи с emoji_type: {e}")
            
            # Выводим информацию о результате преобразования
            if emojized:
                print(f"Исходный текст: {original_text[:50]}...")
                print(f"Преобразованный текст: {text_content[:50]}...")
            else:
                print("Преобразование эмодзи не требовалось или не удалось выполнить")
        except Exception as e:
            print(f"Предупреждение при обработке эмодзи: {e}, используем исходный текст")
        
        # Разбиваем текст на строки, чтобы он поместился в указанной области
        lines = []
        current_line = ""
        
        # Разбиваем по словам, учитывая пробелы и переносы строк
        words = []
        for line in text_content.split('\n'):
            if line.strip():  # Если строка не пустая
                words.extend(line.split())
                words.append('\n')  # Добавляем маркер переноса строки
            else:
                words.append('\n')  # Пустая строка - просто перенос
        
        for word in words:
            if word == '\n':  # Если это маркер переноса строки
                if current_line:
                    lines.append(current_line)
                    current_line = ""
                continue
                
            test_line = current_line + " " + word if current_line else word
            # Проверяем, поместится ли строка по ширине
            text_size = draw.textlength(test_line, font=font)
            if text_size <= text_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word
        
        if current_line:
            lines.append(current_line)
        
        # Рисуем текст на изображении
        line_height = 30  # Уменьшенная высота строки для меньшего шрифта
        
        # Проверяем, поместится ли весь текст по высоте
        total_text_height = len(lines) * line_height
        if total_text_height > text_height:
            # Если текст не помещается, уменьшаем межстрочный интервал
            line_height = min(line_height, text_height / len(lines))
        
        # Рисуем текст с поддержкой эмодзи и кириллицы
        for i, line in enumerate(lines):
            y_position = text_y + i * line_height
            # Проверяем, не вышли ли за нижнюю границу
            if y_position + line_height <= text_y + text_height:
                # Улучшенный рендеринг текста с эмодзи
                if 'emoji_font' in locals() and emoji_font is not None:
                    # Сначала выявляем все эмодзи и их позиции
                    emoji_positions = []
                    # Временная строка для отрисовки (с замененными эмодзи на пробелы)
                    line_without_emoji = ""
                    
                    # Выявляем все эмодзи и их позиции
                    for char_idx, char in enumerate(line):
                        # Используем библиотеку emoji для более точного определения эмодзи
                        is_emoji = False
                        try:
                            # Проверка по Unicode диапазонам для большинства эмодзи
                            if len(char) == 1:  # Обрабатываем только одиночные символы
                                # Основные диапазоны эмодзи в Unicode
                                emoji_ranges = [
                                    (0x1F000, 0x1FFFF),  # Основной блок эмодзи
                                    (0x2600, 0x27BF),   # Разные символы и дингбаты
                                    (0x2300, 0x23FF),   # Технические символы
                                    (0x2B00, 0x2BFF),   # Разные символы и стрелки
                                    (0x3000, 0x303F),   # CJK символы и знаки препинания
                                    (0xFE00, 0xFE0F)    # Вариативные селекторы
                                ]
                                code_point = ord(char)
                                for start, end in emoji_ranges:
                                    if start <= code_point <= end:
                                        is_emoji = True
                                        break
                            
                            # Используем библиотеку emoji для проверки
                            if hasattr(emoji, 'is_emoji') and emoji.is_emoji(char):
                                is_emoji = True
                                
                            # Дополнительная проверка для эмодзи с модификаторами (составных эмодзи)
                            if len(char) > 1 and any(0x1F000 <= ord(c) <= 0x1FFFF for c in char):
                                is_emoji = True
                        except Exception as e:
                            # Если основные проверки не сработали, используем упрощенную проверку
                            try:
                                is_emoji = ord(char) > 8000
                            except Exception:
                                # Для составных символов, которые нельзя преобразовать в ord()
                                pass
                        
                        if is_emoji:
                            emoji_positions.append((char_idx, char))
                            # Добавляем пробел вместо эмодзи
                            line_without_emoji += " "
                        else:
                            # Добавляем обычный символ
                            line_without_emoji += char
                    
                    # Рисуем текст без эмодзи (с пробелами вместо эмодзи)
                    try:
                        draw.text((text_x, y_position), line_without_emoji, fill="black", font=font, embedded=True, layout_engine=ImageFont.LAYOUT_RAQM)
                    except (TypeError, AttributeError):
                        try:
                            draw.text((text_x, y_position), line_without_emoji, fill="black", font=font, layout_engine=ImageFont.LAYOUT_RAQM)
                        except (TypeError, AttributeError):
                            try:
                                draw.text((text_x, y_position), line_without_emoji, fill="black", font=font, embedded=True)
                            except TypeError:
                                draw.text((text_x, y_position), line_without_emoji, fill="black", font=font)
                    
                    # Теперь рисуем эмодзи поверх текста, используя найденные позиции
                    
                    # Теперь отрисовываем каждый эмодзи с помощью специального шрифта
                    for char_idx, char in emoji_positions:
                        # Вычисляем позицию символа в строке
                        char_width = draw.textlength(line[:char_idx], font=font)
                        
                        # Создаем затемнение под эмодзи (чтобы закрыть основной текст)
                        try:
                            # Определяем ширину символа эмодзи
                            emoji_width = draw.textlength(char, font=emoji_font)

                        except Exception:
                            emoji_width = draw.textlength("😀", font=emoji_font)  # Примерная ширина
                        
                        # Рисуем эмодзи с использованием специального шрифта и сохранением цвета
                        try:
                            # Пробуем несколько вариантов отрисовки, от наиболее к наименее предпочтительному
                            # Создаем более крупное временное изображение для отрисовки эмодзи
                            emoji_size = 72  # Значительно увеличиваем размер для лучшего качества
                            emoji_img = Image.new('RGBA', (emoji_size, emoji_size), (0, 0, 0, 0))  # Прозрачное изображение
                            emoji_draw = ImageDraw.Draw(emoji_img)
                            
                            # Метод 1: Отрисовка на временном изображении с большим размером
                            try:
                                # Помещаем эмодзи в центр временного изображения
                                try:
                                    # Пробуем с RAQM для лучшей поддержки эмодзи
                                    emoji_draw.text((emoji_size//4, emoji_size//4), char, font=emoji_font, fill=(0, 0, 0, 255), layout_engine=ImageFont.LAYOUT_RAQM)
                                except (TypeError, AttributeError):
                                    # Если RAQM не доступен, используем стандартный метод
                                    emoji_draw.text((emoji_size//4, emoji_size//4), char, font=emoji_font, fill=(0, 0, 0, 255))
                                
                                # Проверяем, есть ли непрозрачные пиксели (содержимое)
                                has_content = False
                                for y in range(emoji_size):
                                    for x in range(emoji_size):
                                        pixel = emoji_img.getpixel((x, y))
                                        if pixel[3] > 0:  # Проверка альфа-канала
                                            has_content = True
                                            break
                                    if has_content:
                                        break
                                
                                if has_content:
                                    # Масштабируем до нужного размера (около 30-35 пикселей высоты)
                                    # Уменьшаем размер, чтобы лучше соответствовать тексту
                                    target_height = 24
                                    ratio = target_height / emoji_size
                                    resized_width = int(emoji_size * ratio)
                                    emoji_img = emoji_img.resize((resized_width, target_height), Image.LANCZOS)
                                    
                                    # Накладываем на основное изображение со смещением на 3 пикселя влево от текущей позиции
                                    img.paste(emoji_img, (text_x + int(char_width) - 7, y_position), emoji_img)
                                    print(f"Отрисован эмодзи {repr(char)} методом композиции с полной обработкой")
                                else:
                                    # Метод 2: Если в первом методе не получилось - пробуем другой подход с Windows Emoji
                                    try:
                                        # Попытка использовать Windows Segoe UI Emoji с цветом
                                        win_emoji_font_path = os.path.join(os.environ['WINDIR'], 'Fonts', 'seguiemj.ttf')
                                        if os.path.exists(win_emoji_font_path):
                                            try:
                                                # Загружаем шрифт с поддержкой цветных эмодзи
                                                win_emoji_font = ImageFont.truetype(win_emoji_font_path, 28, layout_engine=ImageFont.LAYOUT_RAQM, embedded_color=True)
                                            except (TypeError, AttributeError):
                                                try:
                                                    # Пробуем без layout_engine
                                                    win_emoji_font = ImageFont.truetype(win_emoji_font_path, 28, embedded_color=True)
                                                except (TypeError, AttributeError):
                                                    # Стандартный способ загрузки шрифта
                                                    win_emoji_font = ImageFont.truetype(win_emoji_font_path, 28)
                                            
                                            # Создаем временное RGBA изображение для цветного эмодзи
                                            temp_emoji_img = Image.new('RGBA', (40, 40), (255, 255, 255, 0))
                                            temp_emoji_draw = ImageDraw.Draw(temp_emoji_img)
                                            
                                            # Рисуем цветной эмодзи на временном изображении
                                            try:
                                                # Цветные эмодзи с embedded=True и embedded_color=True
                                                temp_emoji_draw.text((int(5), int(5)), char, font=win_emoji_font, embedded=True, embedded_color=True)
                                            except (TypeError, AttributeError):
                                                try: 
                                                    # Пробуем только с embedded_color
                                                    temp_emoji_draw.text((int(5), int(5)), char, font=win_emoji_font, embedded_color=True)
                                                except (TypeError, AttributeError):
                                                    try:
                                                        # Пробуем с RAQM без цвета
                                                        temp_emoji_draw.text((int(5), int(5)), char, font=win_emoji_font, layout_engine=ImageFont.LAYOUT_RAQM)
                                                    except (TypeError, AttributeError):
                                                        # Стандартный метод
                                                        temp_emoji_draw.text((int(5), int(5)), char, font=win_emoji_font)
                                                
                                            # Накладываем временное изображение на основное со смещением на 7 пикселей влево от текущей позиции
                                            img.paste(temp_emoji_img, (text_x + int(char_width) - 7, y_position), temp_emoji_img)
                                            print(f"Отрисован цветной эмодзи {repr(char)} с использованием Windows Emoji шрифта")
                                        else:
                                            # Запасной вариант - просто пробуем обычную отрисовку
                                            try:
                                                draw.text((text_x + char_width - 7, y_position), char, font=win_emoji_font, fill=(0, 0, 0, 255), layout_engine=ImageFont.LAYOUT_RAQM)
                                            except (TypeError, AttributeError):
                                                draw.text((text_x + char_width - 7, y_position), char, font=win_emoji_font, fill=(0, 0, 0, 255))
                                            print(f"Отрисован эмодзи {repr(char)} прямым методом")
                                    except Exception as e:
                                        print(f"Ошибка при отрисовке Windows Emoji: {e}")
                                        draw.text((text_x + char_width - 7, y_position), char, font=font, fill=(0, 0, 0, 255))
                                        print(f"Отрисован эмодзи {repr(char)} базовым шрифтом текста")
                            except Exception as e:
                                print(f"Ошибка при первичной отрисовке эмодзи: {e}, пробуем стандартный метод")
                                draw.text((text_x + char_width - 7, y_position), char, font=font, fill=(0, 0, 0, 255))
                                print(f"Отрисован эмодзи {repr(char)} стандартным методом")
                        except Exception as e:
                            print(f"Ошибка при отрисовке эмодзи {repr(char)}: {e}")
                else:
                    # Если шрифт Noto Color Emoji недоступен, используем стандартный метод
                    # Но всё равно пытаемся обеспечить наилучшее отображение эмодзи
                    try:
                        # Проверяем, содержит ли строка эмодзи
                        has_emoji = any(emoji.is_emoji(char) if hasattr(emoji, 'is_emoji') else (ord(char) > 8000) for char in line)
                        if has_emoji:
                            print(f"Строка содержит эмодзи, но специальный шрифт для эмодзи недоступен, качество отображения может быть снижено")
                        
                        # Пробуем с параметром embedded для лучшей поддержки Unicode
                        draw.text((text_x, y_position), line, fill="black", font=font, embedded=True)
                    except TypeError:
                        # Если нет параметра embedded, используем базовый вызов
                        draw.text((text_x, y_position), line, fill="black", font=font)
        
        # Сохраняем изображение во временный файл
        try:
            # Создаем временный файл с расширением .png
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
            temp_file.close()
            
            # Сохраняем изображение в файл
            img.save(temp_file.name, 'PNG')
            
            return temp_file.name
        except Exception as e:
            print(f"Ошибка при сохранении изображения во временный файл: {e}")
            return None
    except Exception as e:
        print(f"Ошибка при создании изображения с текстом: {e}")
        return None

def print_image_silent_gdi(image_path, printer_name=None, paper_size='A5'):
    """Тихая печать изображения на лист указанного формата.
    Обрезает и масштабирует изображение под printable area принтера.
    
    Аргументы:
        image_path: путь к изображению для печати
        printer_name: имя принтера (если None, будет использован принтер по умолчанию)
        paper_size: формат бумаги ('A5' по умолчанию)
    """
    if not sys.platform.startswith('win32'):
        print("Печать доступна только на Windows.")
        return False
    if not WINDOWS_PRINT_AVAILABLE:
        print("Ошибка: нет pywin32/Pillow.")
        return False
    if not os.path.exists(image_path):
        print(f"Ошибка: файл '{image_path}' не найден.")
        return False
    try:
        img = Image.open(image_path)
        if img.mode == 'RGBA' or 'A' in img.info.get('transparency', ()):
            bg = Image.new("RGB", img.size, (255,255,255))
            bg.paste(img, mask=img.split()[3])
            img = bg
        elif img.mode != 'RGB':
            img = img.convert('RGB')
    except Exception as e:
        print(f"Ошибка открытия '{image_path}': {e}")
        return False
    if printer_name is None:
        try:
            printer_name = win32print.GetDefaultPrinter()
        except Exception as e:
            print(f"Не удалось получить принтер по умолчанию: {e}")
            img.close()
            return False
    try:
        hprinter = win32print.OpenPrinter(printer_name)
    except Exception as e:
        print(f"Не удалось открыть принтер '{printer_name}': {e}")
        img.close()
        return False
        
    # Настраиваем формат бумаги, если указан
    if paper_size == 'A5':
        try:
            # Получаем текущие настройки принтера
            devmode = win32print.GetPrinter(hprinter, 2).get('pDevMode')
            if devmode:
                # Устанавливаем формат бумаги A5 (код 11)
                devmode.PaperSize = 11  # DMPAPER_A5
                win32print.SetPrinter(hprinter, 2, None, devmode)
                print(f"Установлен формат бумаги A5 для принтера '{printer_name}'")
        except Exception as e:
            print(f"Не удалось установить формат бумаги A5: {e}")
            # Продолжаем печать с текущими настройками
    success = False
    hdc = mem_dc = bitmap = None
    try:
        hdc = win32ui.CreateDC()
        hdc.CreatePrinterDC(printer_name)
        pw = hdc.GetDeviceCaps(win32con.HORZRES)
        ph = hdc.GetDeviceCaps(win32con.VERTRES)
        iw, ih = img.size
        ar_img = iw / ih
        ar_page = pw / ph
        if ar_img > ar_page:
            src_h = ih
            src_w = int(src_h * ar_page)
            src_x = (iw - src_w) // 2
            src_y = 0
        else:
            src_w = iw
            src_h = int(src_w / ar_page)
            src_x = 0
            src_y = (ih - src_h) // 2
        crop_box = (src_x, src_y, src_x + src_w, src_y + src_h)
        img_cropped = img.crop(crop_box)
        hdc.StartDoc(f"Print: {os.path.basename(image_path)}")
        hdc.StartPage()
        mem_dc = hdc.CreateCompatibleDC()
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(hdc, src_w, src_h)
        old = mem_dc.SelectObject(bitmap)
        dib = ImageWin.Dib(img_cropped)
        dib.expose(mem_dc.GetHandleAttrib())
        win32gui.StretchBlt(
            hdc.GetSafeHdc(), 0, 0, pw, ph,
            mem_dc.GetSafeHdc(), 0, 0, src_w, src_h,
            win32con.SRCCOPY
        )
        mem_dc.SelectObject(old)
        hdc.EndPage()
        hdc.EndDoc()
        success = True
        print(f"'{os.path.basename(image_path)}' напечатано на '{printer_name}'")
    except Exception as e:
        print(f"Ошибка печати GDI: {e}")
        try:
            if hdc and hdc.GetSafeHdc():
                hdc.AbortDoc()
        except:
            pass
    finally:
        img.close()
        if bitmap:
            try:
                win32gui.DeleteObject(bitmap.GetHandle())
            except:
                pass
        if mem_dc:
            try:
                mem_dc.DeleteDC()
            except:
                pass
        if hdc:
            try:
                hdc.DeleteDC()
            except:
                pass
        try:
            win32print.ClosePrinter(hprinter)
        except:
            pass
    return success

def main():
    if not sys.platform.startswith('win32'):
        print("Скрипт работает только на Windows.")
        return
    if not WINDOWS_PRINT_AVAILABLE:
        print("Установите 'pywin32' и 'Pillow'.")
        return
    
    # Проверяем наличие шаблона изображения
    if not os.path.exists(TEMPLATE_IMAGE):
        print(f"Ошибка: шаблон изображения не найден по пути '{TEMPLATE_IMAGE}'")
        return
    
    # Инициализация S3 клиента
    s3_client = get_s3_client()
    if s3_client is None:
        print("Невозможно продолжить без S3 клиента.")
        return
    
    # Загрузка истории печати
    printed_files = load_printed_files()
    print(f"Загружено {len(printed_files)} записей о ранее напечатанных файлах.")
    
    # Получаем начальное состояние бакета
    print(f"Отслеживаем S3 бакет '{S3_BUCKET_NAME}' на наличие TXT файлов...")
    current_files = list_files_in_s3_bucket(s3_client, S3_BUCKET_NAME)
    
    # При запуске обрабатываем все ненапечатанные файлы
    print("Проверка всех файлов в S3 бакете на наличие необработанных...")
    for key, last_modified in current_files.items():
        # Проверяем, является ли файл текстовым
        if not key.lower().endswith(TXT_EXTENSION):
            continue
            
        # Проверяем, был ли файл уже обработан
        if key not in printed_files:
            print(f"Найден необработанный файл в S3: {key}")
            
            # Скачиваем файл из S3
            temp_txt_path = download_file_from_s3(s3_client, S3_BUCKET_NAME, key)
            if temp_txt_path:
                try:
                    # Читаем текст из файла
                    text_content = read_text_from_file(temp_txt_path)
                    if text_content is not None:
                        # Создаем изображение с текстом на основе шаблона
                        image_with_text_path = create_image_with_text(TEMPLATE_IMAGE, text_content)
                        if image_with_text_path:
                            try:
                                # Печатаем изображение
                                if print_image_silent_gdi(image_with_text_path):
                                    # Сохраняем информацию о печати
                                    save_printed_file(key)
                                    printed_files.add(key)
                                    print(f"Файл {key} успешно обработан и напечатан")
                            finally:
                                # Удаляем временный файл с изображением
                                try:
                                    os.unlink(image_with_text_path)
                                except Exception as e:
                                    print(f"Ошибка при удалении временного файла изображения: {e}")
                finally:
                    # Удаляем временный текстовый файл
                    try:
                        os.unlink(temp_txt_path)
                    except Exception as e:
                        print(f"Ошибка при удалении временного текстового файла: {e}")
    
    print("Проверка завершена, переходим в режим мониторинга новых файлов")
    
    # Сохраняем текущее состояние бакета
    known_files = current_files
    last_check_time = datetime.datetime.now(datetime.timezone.utc)
    
    try:
        while True:
            time.sleep(CHECK_INTERVAL_SECONDS)
            
            # Получаем текущее состояние бакета
            current_files = list_files_in_s3_bucket(s3_client, S3_BUCKET_NAME)
            
            # Проверяем новые или измененные файлы
            for key, last_modified in current_files.items():
                # Проверяем, является ли файл текстовым
                if not key.lower().endswith(TXT_EXTENSION):
                    continue
                
                # Проверяем, новый ли это файл или был ли он изменен с момента последней проверки
                is_new = key not in known_files
                is_modified = (key in known_files and last_modified > known_files[key])
                is_not_printed = key not in printed_files
                
                # Если файл новый или изменен и не был напечатан ранее
                if (is_new or is_modified) and is_not_printed:
                    print(f"Новый текстовый файл в S3: {key}")
                    
                    # Скачиваем файл из S3
                    temp_txt_path = download_file_from_s3(s3_client, S3_BUCKET_NAME, key)
                    if temp_txt_path:
                        try:
                            # Читаем текст из файла
                            text_content = read_text_from_file(temp_txt_path)
                            if text_content is not None:
                                # Создаем изображение с текстом на основе шаблона
                                image_with_text_path = create_image_with_text(TEMPLATE_IMAGE, text_content)
                                if image_with_text_path:
                                    try:
                                        # Печатаем изображение
                                        if print_image_silent_gdi(image_with_text_path):
                                            # Сохраняем информацию о печати
                                            save_printed_file(key)
                                            printed_files.add(key)
                                    finally:
                                        # Удаляем временный файл с изображением
                                        try:
                                            os.unlink(image_with_text_path)
                                        except Exception as e:
                                            print(f"Ошибка при удалении временного файла изображения: {e}")
                        except Exception as e:
                            print(f"Ошибка при обработке файла {key}: {e}")
                        finally:
                            # Удаляем временный текстовый файл
                            if temp_txt_path and os.path.exists(temp_txt_path):
                                try:
                                    os.unlink(temp_txt_path)
                                except Exception as e:
                                    print(f"Ошибка при удалении временного текстового файла: {e}")
            
            # Обновляем известные файлы
            known_files = current_files
            
    except KeyboardInterrupt:
        print("Остановлено.")
    except Exception as e:
        print(f"Критическая ошибка: {e}")

if __name__ == "__main__":
    main()
