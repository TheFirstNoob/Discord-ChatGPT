import asyncio
import pkg_resources
from src.bot import run_discord_bot
from packaging import version
import sys

REQUIREMENTS_FILE = "requirements.txt"

async def check_library_versions():
    try:
        with open(REQUIREMENTS_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                if ";" in line:
                    package_spec, marker = line.split(";", 1)

                    try:
                        # Need more effective check python version for correct audio-lts check
                        if not eval(marker, {"python_version": sys.version[:3]}):
                            continue
                    except Exception as e:
                        print(f"\n[WARNING] Не удалось оценить environment marker '{marker}': {e}. Пакет '{package_spec}' будет пропущен.\n")
                        continue
                else:
                    package_spec = line

                parts = package_spec.split("==")
                library_name = parts[0].strip()
                required_version_str = parts[1].strip() if len(parts) > 1 else None

                try:
                    installed_version = pkg_resources.get_distribution(library_name).version
                    installed_version_parsed = version.parse(installed_version)

                    if required_version_str:
                        required_version = version.parse(required_version_str)
                        if installed_version_parsed < required_version:
                            print(f"\n[WARNING] Библиотека '{library_name}' устарела. Требуется версия >= {required_version_str}, у вас установлена {installed_version}.")
                            print(f"  Пожалуйста, обновите библиотеку с помощью команды: pip install --upgrade '{library_name}'\n")
                        elif installed_version_parsed > required_version:
                            print(f"\n[WARNING] Библиотека '{library_name}' новее требуемой. Требуется версия <= {required_version_str}, у вас установлена {installed_version}.")
                            print("  Возможна нестабильная работа проекта.\n")
                    else:
                        print(f"\n[INFO] Библиотека '{library_name}' установлена (версия {installed_version}), но версия не указана в {REQUIREMENTS_FILE}.\n")

                except pkg_resources.DistributionNotFound:
                    print(f"\n[ERROR] Библиотека '{library_name}' не установлена.")
                    print(f"  Пожалуйста, установите все зависимости с помощью команды: pip install -r {REQUIREMENTS_FILE}\n")
                    print(f"  Или установите только эту библиотеку с помощью команды: pip install '{library_name}'\n")
                except Exception as e:
                    print(f"\n[ERROR] Произошла ошибка при проверке версии библиотеки '{library_name}': {e}\n")

    except FileNotFoundError:
        print(f"\n[ERROR] Файл {REQUIREMENTS_FILE} не найден.\n")
    except Exception as e:
        print(f"\n[ERROR] Произошла ошибка при чтении файла {REQUIREMENTS_FILE}: {e}\n")


async def main():
    await check_library_versions()
    await run_discord_bot()

if __name__ == '__main__':
    asyncio.run(main())
