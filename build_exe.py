"""
=============================================================================
Скрипт упаковки ADS1256 GUI в EXE файл
=============================================================================
Использует PyInstaller для создания standalone приложения

Требования:
  pip install pyinstaller

Использование:
  python build_exe.py

На выходе:
  dist/ADS1256_EEG_Recorder.exe (~200 МБ)
  
=============================================================================
"""

import os
import sys
import subprocess
import shutil

print("="*70)
print("  ADS1256 EEG Recorder - Сборка EXE")
print("="*70)

# Проверка PyInstaller
try:
    import PyInstaller
    print("✅ PyInstaller установлен")
except ImportError:
    print("❌ PyInstaller не найден!")
    print("   Установите: pip install pyinstaller")
    input("Enter для выхода...")
    sys.exit(1)

# Проверка наличия исходников
required_files = [
    'ads1256_gui.py',
    'ads1256_receiver.py'
]

missing = [f for f in required_files if not os.path.exists(f)]
if missing:
    print(f"❌ Отсутствуют файлы: {missing}")
    input("Enter для выхода...")
    sys.exit(1)

print("✅ Все исходники найдены")

# Очистка предыдущих сборок
if os.path.exists('build'):
    shutil.rmtree('build')
    print("🧹 Очищен каталог build/")

if os.path.exists('dist'):
    shutil.rmtree('dist')
    print("🧹 Очищен каталог dist/")

# Параметры сборки PyInstaller
#
# --onefile         - один EXE файл (альтернатива: --onedir для папки)
# --windowed        - без консольного окна (для GUI)
# --name            - имя выходного файла
# --icon            - иконка (если есть)
# --add-data        - дополнительные файлы
# --hidden-import   - скрытые импорты которые PyInstaller не видит
#

pyinstaller_args = [
    'pyinstaller',
    '--onefile',              # Один EXE файл
    '--windowed',             # GUI без консоли
    '--name=ADS1256_EEG_Recorder',
    '--hidden-import=PyQt5',
    '--hidden-import=pyqtgraph',
    '--hidden-import=serial',
    '--hidden-import=numpy',
    '--clean',                # Очистка кеша
    'ads1256_gui.py'
]

print("\n" + "="*70)
print("  Запуск PyInstaller...")
print("="*70)
print("Это займёт 2-5 минут...")
print()

# Запуск PyInstaller
try:
    result = subprocess.run(pyinstaller_args, check=True)
    
    print("\n" + "="*70)
    print("✅ Сборка завершена успешно!")
    print("="*70)
    
    exe_path = os.path.join('dist', 'ADS1256_EEG_Recorder.exe')
    
    if os.path.exists(exe_path):
        size_mb = os.path.getsize(exe_path) / (1024*1024)
        print(f"\n📦 EXE файл:")
        print(f"   Путь: {os.path.abspath(exe_path)}")
        print(f"   Размер: {size_mb:.1f} МБ")
        
        # Инструкции
        print(f"\n📋 Что дальше:")
        print(f"   1. Найдите файл: {os.path.abspath(exe_path)}")
        print(f"   2. Скопируйте его на другой ПК")
        print(f"   3. Запустите двойным кликом")
        print(f"   4. Драйвер CH340 должен быть установлен на целевом ПК!")
        
    else:
        print("❌ EXE файл не найден после сборки")
        
except subprocess.CalledProcessError as e:
    print(f"\n❌ Ошибка при сборке: {e}")
    print("\nПопробуйте:")
    print("  1. Обновить PyInstaller: pip install --upgrade pyinstaller")
    print("  2. Проверить что все библиотеки установлены")
    print("  3. Запустить от имени администратора")

print("\n")
input("Enter для выхода...")
