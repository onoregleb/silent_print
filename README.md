# AutoPrint: Автоматическая печать изображений из S3 (Windows)

Этот скрипт автоматически отслеживает S3 бакет и отправляет новые изображения на печать на принтер Windows, используя GDI (Graphics Device Interface). Поддерживаются форматы: `.jpg`, `.jpeg`, `.png`, `.gif`.

---

## Установка

1. Убедитесь, что вы используете **Windows**.
2. Установите Python 3.10+.
3. Установите зависимости:

```bash
pip install -r requirements.txt
```

---

## Запуск

### Печать из Yandex Cloud S3 бакета

1. Настройте AWS CLI для работы с Yandex Cloud:

```bash
aws configure set aws_access_key_id YOUR_YANDEX_ACCESS_KEY_ID
aws configure set aws_secret_access_key YOUR_YANDEX_SECRET_ACCESS_KEY
aws configure set default.region ru-central1
aws configure set default.output json
```

2. Отредактируйте файл `silent_print_s3.py` и укажите имя вашего S3 бакета в Yandex Cloud в переменной `S3_BUCKET_NAME`.

3. Запустите скрипт:

```bash
python silent_print_s3.py
```

4. Скрипт будет каждую секунду проверять наличие новых изображений в Yandex Cloud S3 бакете и печатать их на принтер по умолчанию.

5. Информация о напечатанных файлах сохраняется в файле `printed_files.txt`.

### Загрузка файлов в Yandex Cloud S3

Для загрузки файлов в бакет используйте AWS CLI с указанием endpoint-url:

```bash
aws --endpoint-url=https://storage.yandexcloud.net s3 cp ./путь/к/файлу.png s3://имя-бакета/имя-файла.png
```

Например, для загрузки файла из папки photo:

```bash
aws --endpoint-url=https://storage.yandexcloud.net s3 cp ./photo/image.png s3://wikilect-ecom-expo-may-2025/image.png
```

Чтобы остановить любой из скриптов — нажмите `Ctrl + C`.

---

## Как включить цветную печать по умолчанию (Canon LBP631Cw)

### Через панель управления Windows:

1. Откройте **Панель управления** → **Устройства и принтеры**
2. Найдите **Canon LBP631Cw**, нажмите правой кнопкой мыши → **Настройки печати**
3. Перейдите на вкладку **Цвет/Черно-белый** или аналогичную, и выберите **Цвет**
4. Нажмите **OK**/Применить

### Через свойства драйвера:

1. Откройте **Свойства принтера** → вкладка **Дополнительно**
2. Нажмите **Параметры печати по умолчанию**
3. Установите цветной режим
4. Сохраните изменения

---


