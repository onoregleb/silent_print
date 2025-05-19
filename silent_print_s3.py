import time
import os
import sys
import json
import win32con
import win32print
import win32ui
import win32gui
from PIL import Image, ImageWin
import boto3
from botocore.exceptions import ClientError
import tempfile
import datetime

WINDOWS_PRINT_AVAILABLE = True
S3_BUCKET_NAME = 'wikilect-ecom-expo-may-2025' 
CHECK_INTERVAL_SECONDS = 1  # Проверка каждую секунду
IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif']
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

def print_image_silent_gdi(image_path, printer_name=None):
    """Тихая печать изображения на весь лист (без полей по возможности).
    Обрезает и масштабирует изображение под printable area принтера."""
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
    
    # Инициализация S3 клиента
    s3_client = get_s3_client()
    if s3_client is None:
        print("Невозможно продолжить без S3 клиента.")
        return
    
    # Загрузка истории печати
    printed_files = load_printed_files()
    print(f"Загружено {len(printed_files)} записей о ранее напечатанных файлах.")
    
    # Получаем начальное состояние бакета
    print(f"Отслеживаем S3 бакет '{S3_BUCKET_NAME}'...")
    last_check_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=60)
    known_files = list_files_in_s3_bucket(s3_client, S3_BUCKET_NAME)
    
    try:
        while True:
            time.sleep(CHECK_INTERVAL_SECONDS)
            
            # Получаем текущее состояние бакета
            current_files = list_files_in_s3_bucket(s3_client, S3_BUCKET_NAME)
            
            # Проверяем новые или измененные файлы
            for key, last_modified in current_files.items():
                # Проверяем, является ли файл изображением
                if not any(key.lower().endswith(ext) for ext in IMAGE_EXTENSIONS):
                    continue
                
                # Проверяем, новый ли это файл или был ли он изменен с момента последней проверки
                is_new = key not in known_files
                is_modified = (key in known_files and last_modified > known_files[key])
                is_not_printed = key not in printed_files
                
                # Если файл новый или изменен и не был напечатан ранее
                if (is_new or is_modified) and is_not_printed:
                    # Проверяем, был ли файл изменен за последние n секунд
                    time_diff = datetime.datetime.now(datetime.timezone.utc) - last_modified
                    if time_diff.total_seconds() <= 60:  # Проверяем файлы, измененные за последнюю минуту
                        print(f"Новое изображение в S3: {key}")
                        
                        # Скачиваем файл из S3
                        temp_file_path = download_file_from_s3(s3_client, S3_BUCKET_NAME, key)
                        if temp_file_path:
                            try:
                                # Печатаем изображение
                                if print_image_silent_gdi(temp_file_path):
                                    # Сохраняем информацию о печати
                                    save_printed_file(key)
                                    printed_files.add(key)
                            finally:
                                # Удаляем временный файл
                                try:
                                    os.unlink(temp_file_path)
                                except Exception as e:
                                    print(f"Ошибка при удалении временного файла: {e}")
            
            # Обновляем известные файлы
            known_files = current_files
            
    except KeyboardInterrupt:
        print("Остановлено.")
    except Exception as e:
        print(f"Критическая ошибка: {e}")

if __name__ == "__main__":
    main()
