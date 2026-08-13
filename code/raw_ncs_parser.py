import os
import sys
import json
import re
import subprocess
from pathlib import Path

# --- Пути ---
BASE_DIR = Path("/home/nexpg/RawBL4ToCutBDInterpreter")
GAME_PAKS_DIR = Path("/home/nexpg/Borderlands 4/OakGame/Content/Paks")
BL4_BIN = BASE_DIR / "bl4"

RAW_BIN_DIR = BASE_DIR / "data" / "ncs_raw_bin"
RAW_JSON_DIR = BASE_DIR / "data" / "ncs_raw_json"

def init_directories():
    RAW_BIN_DIR.mkdir(parents=True, exist_ok=True)
    RAW_JSON_DIR.mkdir(parents=True, exist_ok=True)

def check_env():
    if not BL4_BIN.exists():
        print(f"❌ Ошибка: Исполняемый файл bl4 не найден по пути {BL4_BIN}")
        sys.exit(1)
    if not GAME_PAKS_DIR.exists():
        print(f"❌ Ошибка: Директория игры не найдена по пути {GAME_PAKS_DIR}")
        sys.exit(1)
    print("✅ Окружение успешно проверено.")

def natural_sort_key(path: Path):
    """Сортировка патчей по возрастанию номера (pakchunk0 -> pakchunk10)"""
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', path.name)]

def step1_decompress_raw_ncs():
    """Распаковка сырых NCS-бинарников (.bin)"""
    print("\n🚀 [1/2] Распаковка сырых NCS-бинарников (.bin) из PAK-файлов...")
    
    pak_files = list(GAME_PAKS_DIR.glob("*.pak")) + list(GAME_PAKS_DIR.glob("*.utoc"))
    if not pak_files:
        print(f"❌ Файлы .pak/.utoc не найдены в {GAME_PAKS_DIR}")
        sys.exit(1)

    pak_files.sort(key=natural_sort_key)

    for pak in pak_files:
        print(f"  -> Извлечение из: {pak.name}")
        cmd = [
            str(BL4_BIN), "ncs", "decompress",
            str(pak),
            "-o", str(RAW_BIN_DIR),
            "--raw"
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Удаляем 0-байтовые пустышки
    bin_files = list(RAW_BIN_DIR.rglob("*.bin")) + list(RAW_BIN_DIR.rglob("*.ncs"))
    removed_empty = 0
    for bf in bin_files:
        if bf.stat().st_size == 0:
            bf.unlink()
            removed_empty += 1

    print(f"✅ Распаковка завершена. Бинарников (.bin): {len(list(RAW_BIN_DIR.rglob('*')))}")

def step2_convert_bin_to_raw_json():
    """Конвертация каждого .bin в ПОЛНЫЙ СЫРОЙ JSON (без потери тегов)"""
    print("\n🚀 [2/2] Дамп всех .bin файлов в Сырые Необрезанные JSON...")
    
    bin_files = [f for f in RAW_BIN_DIR.rglob("*") if f.is_file() and f.stat().st_size > 0]
    bin_files.sort(key=natural_sort_key)
    
    saved_json_count = 0
    skipped_empty_count = 0

    for bin_file in bin_files:
        rel_path = bin_file.relative_to(RAW_BIN_DIR)
        out_json_path = RAW_JSON_DIR / rel_path.with_suffix(".json")
        out_json_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            str(BL4_BIN), "ncs", "extract",
            str(bin_file),
            "-t", "binary",
            "--json"
        ]
        
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        parsed_json = None
        is_valid = False

        if res.returncode == 0 and res.stdout.strip():
            try:
                parsed_json = json.loads(res.stdout.strip())
                if isinstance(parsed_json, dict) and len(parsed_json) > 0:
                    is_valid = any(bool(v) for v in parsed_json.values())
                elif isinstance(parsed_json, list) and len(parsed_json) > 0:
                    is_valid = True
            except json.JSONDecodeError:
                is_valid = False

        # Альтернатива show --json если extract -t binary дал пустоту
        if not is_valid:
            cmd_alt = [str(BL4_BIN), "ncs", "show", str(bin_file), "--json"]
            res_alt = subprocess.run(cmd_alt, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res_alt.returncode == 0 and res_alt.stdout.strip():
                try:
                    parsed_json = json.loads(res_alt.stdout.strip())
                    if parsed_json and len(parsed_json) > 0:
                        is_valid = True
                except json.JSONDecodeError:
                    is_valid = False

        if is_valid and parsed_json is not None:
            with open(out_json_path, "w", encoding="utf-8") as f:
                json.dump(parsed_json, f, ensure_ascii=False, indent=2)
            saved_json_count += 1
        else:
            skipped_empty_count += 1
            if out_json_path.exists():
                out_json_path.unlink()

    print(f"✅ Сырые JSON сгенерированы: {saved_json_count} шт.")

def main():
    init_directories()
    check_env()
    step1_decompress_raw_ncs()
    step2_convert_bin_to_raw_json()
    print("\n🎉 ВСЕ СЫРЫЕ ДАННЫЕ ГОТОВЫ К ПАРСИНГУ В JUPYTER NOTEBOOK!")
    print(f"📁 Сырые полные файлы с абсолютно всей инфой лежат в: {RAW_JSON_DIR}")

if __name__ == "__main__":
    main()