#!/usr/bin/env python3
import argparse
import glob
import shutil
import warnings
from pathlib import Path
from typing import Iterable, List

import whisper
from whisper.tokenizer import LANGUAGES


def expand_inputs(patterns: Iterable[str]) -> List[Path]:
    files: List[Path] = []
    for pattern in patterns:
        matched = [Path(p) for p in glob.glob(pattern)]
        if matched:
            files.extend(matched)
        else:
            candidate = Path(pattern)
            if candidate.exists():
                files.append(candidate)
    deduped = []
    seen = set()
    for path in files:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            deduped.append(path)
    return deduped


def transcribe_files(
    files: List[Path], model_name: str, language: str, overwrite: bool
) -> None:
    if not files:
        raise SystemExit("Nenhum arquivo encontrado para o padrão informado.")

    warnings.filterwarnings(
        "ignore",
        message="FP16 is not supported on CPU; using FP32 instead",
    )

    if shutil.which("ffmpeg") is None:
        raise SystemExit(
            "ffmpeg não encontrado no PATH. Instale o ffmpeg e tente novamente.\n"
            "Execute: \n"
            "sudo apt-get update && sudo apt-get install -y ffmpeg"
        )

    normalized_language = language.strip().lower()
    if normalized_language not in LANGUAGES:
        supported = ", ".join(sorted(LANGUAGES.keys()))
        raise SystemExit(
            "Idioma não suportado. Use um código de idioma válido.\n"
            f"Idioma informado: {language}\n"
            f"Idiomas suportados: {supported}"
        )

    model = whisper.load_model(model_name)

    target_files = [path for path in files if not path.is_dir()]
    total = len(target_files)
    processed = 0
    skipped = 0

    try:
        for audio_path in target_files:
            output_path = audio_path.with_suffix(".txt")
            if output_path.exists() and not overwrite:
                skipped += 1
                print(f"PULADO (já existe): {output_path}")
                continue
            result = model.transcribe(str(audio_path), language=normalized_language)
            temp_path = output_path.with_suffix(output_path.suffix + ".tmp")
            temp_path.write_text(
                result.get("text", "").strip() + "\n", encoding="utf-8"
            )
            temp_path.replace(output_path)
            processed += 1
            print(f"OK: {audio_path} -> {output_path}")
    except KeyboardInterrupt:
        remaining = total - processed - skipped
        print("\nInterrompido pelo usuário (Ctrl+C).")
        print(f"Total de arquivos: {total}")
        print(f"Processados: {processed}")
        print(f"Pulados (já existiam): {skipped}")
        print(f"Restantes: {remaining}")
        return


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Transcreve arquivos .opus para .txt usando openai-whisper."
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="Arquivo(s) ou padrão(ões) glob, ex: ./opus/*.opus",
    )
    parser.add_argument(
        "--model",
        default="small",
        help="Modelo Whisper (tiny, base, small, medium, large).",
    )
    parser.add_argument(
        "--language",
        default="pt",
        help="Idioma de transcrição (ex: pt).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Sobrescreve arquivos .txt existentes.",
    )
    args = parser.parse_args()

    files = expand_inputs(args.inputs)
    transcribe_files(files, args.model, args.language, args.overwrite)


if __name__ == "__main__":
    main()
