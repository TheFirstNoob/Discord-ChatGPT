import sys
import asyncio
from packaging import version
from importlib.metadata import distribution, PackageNotFoundError
from src.bot import run_discord_bot
from src.locale_manager import locale_manager as lm

REQUIREMENTS_FILE = "requirements.txt"

def check_python_version():
    python_version = version.parse(sys.version.split()[0])
    required_version = version.parse("3.10.0")

    if python_version < required_version:
        print(f"\n{lm.get('main_python_version_error', version=python_version)}")
        print(f"  {lm.get('main_python_version_error_help')}\n")
        sys.exit(1)

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
                        if not eval(marker, {"python_version": sys.version[:3]}):
                            continue
                    except Exception as e:
                        print(f"\n{lm.get('main_environment_marker_error', marker=marker, error=str(e), package=package_spec)}\n")
                        continue
                else:
                    package_spec = line

                parts = package_spec.split("==")
                library_name = parts[0].strip()
                required_version_str = parts[1].strip() if len(parts) > 1 else None

                try:
                    installed_version = distribution(library_name).version
                    installed_version_parsed = version.parse(installed_version)

                    if required_version_str:
                        required_version = version.parse(required_version_str)
                        if installed_version_parsed < required_version:
                            print(f"\n{lm.get('main_library_version_warning', library=library_name, required=required_version_str, installed=installed_version)}")
                            print(f"  {lm.get('main_library_version_warning_help', library=library_name)}\n")
                            print(f"  {lm.get('main_library_version_warning_unstable')}\n")
                        elif installed_version_parsed > required_version:
                            print(f"\n{lm.get('main_library_version_warning_newer', library=library_name, required=required_version_str, installed=installed_version)}")
                            print(f"  {lm.get('main_library_version_warning_unstable')}\n")
                    else:
                        print(f"\n{lm.get('main_library_version_info', library=library_name, version=installed_version, file=REQUIREMENTS_FILE)}\n")

                except PackageNotFoundError:
                    print(f"\n{lm.get('main_library_not_found', library=library_name)}")
                    print(f"  {lm.get('main_library_not_found_help', file=REQUIREMENTS_FILE)}\n")
                    print(f"  {lm.get('main_library_not_found_help_alt', library=library_name)}\n")
                except Exception as e:
                    print(f"\n{lm.get('main_library_check_error', library=library_name, error=str(e))}\n")

    except FileNotFoundError:
        print(f"\n{lm.get('main_requirements_not_found', file=REQUIREMENTS_FILE)}\n")
    except Exception as e:
        print(f"\n{lm.get('main_requirements_read_error', file=REQUIREMENTS_FILE, error=str(e))}\n")

async def main():
    check_python_version()

    await check_library_versions()

    await run_discord_bot()

if __name__ == '__main__':
    asyncio.run(main())