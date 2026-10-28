# Стек и установка

Бот не лезет в игру и не читает её память. Он смотрит на скриншоты и тапает, как человек.

| Часть | У меня | Альтернатива для Windows |
| --- | --- | --- |
| Эмулятор | BlueStacks Air (Mac, Apple Silicon) | BlueStacks 5 / LDPlayer / MuMu |
| Управление | ADB: `adb exec-out screencap -p`, `adb shell input tap/swipe`, `keyevent 4` (Back) | то же |
| Язык | Python 3 + venv | то же |
| Кнопки и иконки | OpenCV `matchTemplate` по кропам (шаблонам) | то же |
| Текст (OCR) | Apple Vision через `ocrmac` | EasyOCR / PaddleOCR / Tesseract |
| Расписание | launchd + `pmset` (будит Mac) | Планировщик заданий |
| Отчёт | HTML со скриншотами + уведомление macOS | HTML / Telegram-бот |

## Установка

1. Включите ADB в эмуляторе: Settings → Advanced → Android Debug Bridge.
   У BlueStacks Air он на `127.0.0.1:5555`.
2. Поставьте adb (`brew install android-platform-tools`) и проверьте:
   `adb connect 127.0.0.1:5555 && adb devices`.
3. Создайте окружение: `python3 -m venv .venv && .venv/bin/pip install opencv-python numpy pillow ocrmac`.
   На Windows вместо `ocrmac` поставьте `easyocr`.
4. Игра должна быть на **английском** и в ландшафтной ориентации: все OCR-правила написаны под английские слова.
5. Экран устройства у меня 1920x1080, но бот всегда уменьшает скриншот до **1280x720**
   и работает в этих координатах, а тап пересчитывает обратно. Так все шаблоны и координаты
   живут в одной системе.
6. Пакет Raid на Android: `com.plarium.raidlegends`. Запуск:
   `adb shell monkey -p com.plarium.raidlegends -c android.intent.category.LAUNCHER 1`.

## Шаблоны

Шаблон — это PNG-кроп кнопки, вырезанный из скриншота 1280x720 (`examples/device.py` сохраняет
скриншот уже в этом размере). Вырезайте плотно, без фона вокруг, и только ту часть, которая не меняется:
текст кнопки, а не число на ней. Порог совпадения обычно 0.8; для портретов героев 0.75–0.9.
