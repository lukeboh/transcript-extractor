#!/usr/bin/env python3
import argparse
from pathlib import Path


def collect_txt_files(input_dir: Path) -> list[Path]:
    files = [p for p in input_dir.glob("*.txt") if p.is_file()]
    return sorted(files, key=lambda p: p.stat().st_mtime)


def concatenate_files(input_dir: Path, output_path: Path) -> None:
    files = collect_txt_files(input_dir)
    if not files:
        raise SystemExit("Nenhum arquivo .txt encontrado para concatenar.")

    with output_path.open("w", encoding="utf-8") as out_handle:
        for index, file_path in enumerate(files):
            content = file_path.read_text(encoding="utf-8")
            out_handle.write(f"{file_path.name}\n")
            out_handle.write(content)
            if not content.endswith("\n"):
                out_handle.write("\n")
            if index < len(files) - 1:
                out_handle.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Concatena transcrições .txt em ordem cronológica."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("./opus"),
        help="Diretório com arquivos .txt (padrão: ./opus).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("./transcricoes_concatenadas.txt"),
        help="Arquivo de saída concatenado.",
    )
    args = parser.parse_args()

    concatenate_files(args.input_dir, args.output)


if __name__ == "__main__":
    main()
