#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import glob
import json
import shutil
import subprocess
from pathlib import Path

# ==============================================================================
# КОНФИГУРАЦИЯ ПУТЕЙ ПРОЕКТА
# ==============================================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent
GAME_PAKS_DIR = Path("/home/nexpg/Borderlands 4/OakGame/Content/Paks")
BL4_BIN = PROJECT_ROOT / "bl4"

RAW_NCS_DIR = PROJECT_ROOT / "data" / "raw_ncs"
EXTRACTED_DIR = PROJECT_ROOT / "data" / "extracted"

RAW_NCS_DIR.mkdir(parents=True, exist_ok=True)
EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)


def is_empty_path(path):
    """
    Проверяет, является ли файл или директория пустой/без данных.
    """
    p = Path(path)
    if not p.exists():
        return True

    # Если это директория
    if p.is_dir():
        contents = list(p.rglob("*"))
        if not contents:
            return True
        # Проверяем, есть ли хотя бы один файл больше 10 байт
        has_data = any(f.is_file() and f.stat().st_size > 10 for f in contents)
        return not has_data

    # Если это файл
    if p.is_file():
        if p.stat().st_size < 15:
            return True
        try:
            if p.suffix == '.json':
                with p.open('r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list) and len(data) == 0:
                        return True
                    if isinstance(data, dict):
                        if len(data) == 0:
                            return True
                        if 'items' in data and len(data['items']) == 0:
                            return True
                        if 'drops' in data and len(data['drops']) == 0:
                            return True
            elif p.suffix in ('.tsv', '.txt'):
                with p.open('r', encoding='utf-8') as f:
                    lines = [line.strip() for line in f if line.strip()]
                    if not lines:
                        return True
        except Exception:
            return True

    return False


def clean_path_if_empty(path):
    """
    Удаляет файл или папку, если они оказались пустыми.
    """
    p = Path(path)
    if is_empty_path(p):
        if p.exists():
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
        return True
    return False


def run_cmd_and_clean(cmd, output_path, description=""):
    """
    Запускает команду bl4 и чистит результат, если он пуст.
    """
    print(f"⏳ {description}...")
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out_p = Path(output_path)

    if clean_path_if_empty(out_p):
        print(f"  ❌ Пропущено (нет данных): {out_p.name}")
        return False
    else:
        print(f"  ✅ Успешно сохранено: {out_p.name}")
        return True


def main():
    print("==================================================================")
    print("  FULL BORDERLANDS 4 DATA EXTRACTION PIPELINE")
    print("==================================================================")
    print(f"Корень проекта:     {PROJECT_ROOT}")
    print(f"Путь к пакам игры:  {GAME_PAKS_DIR}")
    print(f"Исполняемый bl4:    {BL4_BIN}")
    print("------------------------------------------------------------------\n")

    if not BL4_BIN.exists():
        print(f"❌ Ошибка: Файл bl4 не найден по пути {BL4_BIN}!")
        print("Пожалуйста, убедись, что файл bl4 скопирован в корень проекта.")
        sys.exit(1)

    # ------------------------------------------------------------------
    # ШАГ 1: Распаковка ВСЕХ NCS-блоков из PAK-файлов с флагом --raw
    # ------------------------------------------------------------------
    print("🚀 [1/8] Распаковка NCS файлов из всех PAK-файлов игры...")
    pak_files = sorted(glob.glob(str(GAME_PAKS_DIR / "*.pak")))
    if not pak_files:
        print(f"❌ Ошибка: Не найдено PAK-файлов в директории {GAME_PAKS_DIR}")
        sys.exit(1)

    for pak in pak_files:
        pak_name = os.path.basename(pak)
        print(f"  -> Распаковка: {pak_name}")
        subprocess.run(
            [str(BL4_BIN), "ncs", "decompress", pak, "-o", str(RAW_NCS_DIR), "--raw"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

    print("  Распаковка бинарников завершена.\n")

    # ------------------------------------------------------------------
    # ШАГ 2: Генерация Манифеста Дропа (Боссы, Шансы, Шайни, Ворлд Дроп)
    # ------------------------------------------------------------------
    print("🚀 [2/8] Извлечение таблиц дропа и источников (drops.json)...")
    drops_json = EXTRACTED_DIR / "drops.json"
    manifest_dir = EXTRACTED_DIR / "manifest"
    cmd_drops = [
        str(BL4_BIN), "drops", "generate", str(RAW_NCS_DIR),
        "-o", str(drops_json),
        "--manifest-dir", str(manifest_dir)
    ]
    run_cmd_and_clean(cmd_drops, drops_json, "Генерация таблицы дропа drops.json")

    # ------------------------------------------------------------------
    # ШАГ 3: Извлечение всех рецептов предметов и их частей (inv*.bin)
    # ------------------------------------------------------------------
    print("\n🚀 [3/8] Извлечение рецептов предметов и модулей (inv*.bin)...")
    inv_files = sorted(glob.glob(str(RAW_NCS_DIR / "inv*.bin")))
    for inv_file in inv_files:
        fname = Path(inv_file).stem
        out_json = EXTRACTED_DIR / f"item_parts_{fname}.json"
        cmd_item_parts = [
            str(BL4_BIN), "ncs", "extract", inv_file,
            "-t", "item-parts", "--json",
            "-o", str(out_json)
        ]
        run_cmd_and_clean(cmd_item_parts, out_json, f"item-parts из {fname}")

    # ------------------------------------------------------------------
    # ШАГ 4: Извлечение Манифеста всех 5300+ частей (Папка parts_manifest)
    # ------------------------------------------------------------------
    print("\n🚀 [4/8] Извлечение глобального Манифеста деталей (parts_manifest)...")
    parts_manifest_path = EXTRACTED_DIR / "parts_manifest.json"
    cmd_manifest = [
        str(BL4_BIN), "ncs", "extract", str(RAW_NCS_DIR),
        "-t", "manifest",
        "-o", str(parts_manifest_path)
    ]
    run_cmd_and_clean(cmd_manifest, parts_manifest_path, "Генерация parts_manifest.json")

    # ------------------------------------------------------------------
    # ШАГ 5: Извлечение Названий предметов, UUIDs и Производителей
    # ------------------------------------------------------------------
    print("\n🚀 [5/8] Извлечение Названий предметов, UUID и Производителей...")
    
    # Названия и UUIDs из файлов названий и инвентаря
    name_source_files = sorted(glob.glob(str(RAW_NCS_DIR / "inv_name_part*.bin"))) + inv_files
    for nfile in name_source_files:
        fname = Path(nfile).stem
        out_json = EXTRACTED_DIR / f"names_{fname}.json"
        cmd_names = [
            str(BL4_BIN), "ncs", "extract", nfile,
            "-t", "names", "--json",
            "-o", str(out_json)
        ]
        run_cmd_and_clean(cmd_names, out_json, f"names из {fname}")

    # Производители
    for inv_file in inv_files:
        fname = Path(inv_file).stem
        out_json = EXTRACTED_DIR / f"mfg_{fname}.json"
        cmd_mfg = [
            str(BL4_BIN), "ncs", "extract", inv_file,
            "-t", "manufacturers", "--json",
            "-o", str(out_json)
        ]
        run_cmd_and_clean(cmd_mfg, out_json, f"manufacturers из {fname}")

    # ------------------------------------------------------------------
    # ШАГ 6: Извлечение специальных конфигураций NCS (Loot, Preferred, Traits)
    # ------------------------------------------------------------------
    print("\n🚀 [6/8] Извлечение специальных конфигурационных таблиц NCS...")
    ncs_types = [
        "itempool", "itempoollist", "loot_config", "preferredparts",
        "attribute", "trait_pool", "vending_machine", "Mission",
        "gbxactor", "achievement"
    ]
    for ntype in ncs_types:
        out_json = EXTRACTED_DIR / f"ncs_config_{ntype}.json"
        cmd_type = [
            str(BL4_BIN), "ncs", "extract", str(RAW_NCS_DIR),
            "-t", ntype, "--json",
            "-o", str(out_json)
        ]
        run_cmd_and_clean(cmd_type, out_json, f"Экстракция конфигурации '{ntype}'")

    # ------------------------------------------------------------------
    # ШАГ 7: Извлечение Сырых Строк (Strings)
    # ------------------------------------------------------------------
    print("\n🚀 [7/8] Извлечение текстовых строк...")
    for sfile in inv_files:
        fname = Path(sfile).stem
        out_tsv = EXTRACTED_DIR / f"strings_{fname}.tsv"
        cmd_strings = [
            str(BL4_BIN), "ncs", "extract", sfile,
            "-t", "strings",
            "-o", str(out_tsv)
        ]
        run_cmd_and_clean(cmd_strings, out_tsv, f"strings из {fname}")

    # ------------------------------------------------------------------
    # ШАГ 8: Декодер серийников и глубокие бинарные AST-структуры
    # ------------------------------------------------------------------
    print("\n🚀 [8/8] Извлечение Декодера серийников и AST-дампов...")
    decoder_json = EXTRACTED_DIR / "serial_decoder.json"
    cmd_decoder = [
        str(BL4_BIN), "ncs", "extract", str(RAW_NCS_DIR),
        "-t", "decoder", "--json",
        "-o", str(decoder_json)
    ]
    run_cmd_and_clean(cmd_decoder, decoder_json, "Декодер серийников serial_decoder.json")

    inv_main = RAW_NCS_DIR / "inv.bin"
    if inv_main.exists():
        out_bin_json = EXTRACTED_DIR / "inv_full_ast.json"
        cmd_ast = [
            str(BL4_BIN), "ncs", "extract", str(inv_main),
            "-t", "binary", "--json",
            "-o", str(out_bin_json)
        ]
        run_cmd_and_clean(cmd_ast, out_bin_json, "Дамп главного inv.bin AST")

    actor_main = RAW_NCS_DIR / "gbxactor.bin"
    if actor_main.exists():
        out_actor_json = EXTRACTED_DIR / "actor_full_ast.json"
        cmd_ast2 = [
            str(BL4_BIN), "ncs", "extract", str(actor_main),
            "-t", "binary", "--json",
            "-o", str(out_actor_json)
        ]
        run_cmd_and_clean(cmd_ast2, out_actor_json, "Дамп главного gbxactor.bin AST")

    print("\n==================================================================")
    print("🎉 ЭКСТРАКЦИЯ УСПЕШНО ЗАВЕРШЕНА!")
    print(f"Все непустые файлы сохранены в:")
    print(f"   {EXTRACTED_DIR}")
    print("==================================================================")


if __name__ == "__main__":
    main()