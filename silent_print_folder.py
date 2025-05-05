import time
import os
import sys
import win32con
import win32print
import win32ui
import win32gui
from PIL import Image, ImageWin

WINDOWS_PRINT_AVAILABLE = True
MONITORED_FOLDER = 'photo'
CHECK_INTERVAL_SECONDS = 3
IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif']

def list_files_in_folder(folder_path):
    """Возвращает множество полных путей к файлам в указанной папке."""
    file_paths = set()
    if not os.path.isdir(folder_path):
        print(f"Ошибка: папка '{folder_path}' не найдена.")
        return file_paths
    try:
        for entry in os.listdir(folder_path):
            full = os.path.join(folder_path, entry)
            if os.path.isfile(full):
                file_paths.add(os.path.abspath(full))
    except Exception as e:
        print(f"Ошибка при чтении '{folder_path}': {e}")
    return file_paths

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
    if not os.path.isdir(MONITORED_FOLDER):
        os.makedirs(MONITORED_FOLDER, exist_ok=True)
    print(f"Отслеживаем папку '{MONITORED_FOLDER}'...")
    known = list_files_in_folder(MONITORED_FOLDER)
    try:
        while True:
            time.sleep(CHECK_INTERVAL_SECONDS)
            current = list_files_in_folder(MONITORED_FOLDER)
            new = current - known
            if new:
                for path in sorted(new):
                    if any(path.lower().endswith(ext) for ext in IMAGE_EXTENSIONS):
                        print(f"Новая картинка: {os.path.basename(path)}")
                        print_image_silent_gdi(path)
                known.update(new)
    except KeyboardInterrupt:
        print("Остановлено.")
    except Exception as e:
        print(f"Критическая ошибка: {e}")

if __name__ == "__main__":
    main()