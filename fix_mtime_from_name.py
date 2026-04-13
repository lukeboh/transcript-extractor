#!/usr/bin/env python3
import argparse
from datetime import datetime
from pathlib import Path
import os


def parse_timestamp_from_name(name: str) -> datetime:
    # Esperado: YYYY-MM-DD HH mm ss no início do nome
    prefix = name[:19]
    return datetime.strptime(prefix, "%Y-%m-%d %H %M %S")


def update_mtime(file_path: Path) -> None:
    timestamp = parse_timestamp_from_name(file_path.name)
    epoch = timestamp.timestamp()
    os.utime(file_path, (epoch, epoch))
    print(f"OK: {file_path} -> {timestamp.isoformat(' ')}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Atualiza mtime/atime baseado no prefixo YYYY-MM-DD HH mm ss do nome."
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="Arquivo(s) ou padrão(ões) glob, ex: ./mp3/*.mp3",
    )
    args = parser.parse_args()

    files = []
    for pattern in args.inputs:
        matched = list(Path().glob(pattern))
        if matched:
            files.extend(matched)
        else:
            candidate = Path(pattern)
            if candidate.exists():
                files.append(candidate)

    if not files:
        raise SystemExit("Nenhum arquivo encontrado para atualizar.")

    for file_path in files:
        if file_path.is_file():
            update_mtime(file_path)


if __name__ == "__main__":
    main()
