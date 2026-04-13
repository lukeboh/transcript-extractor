#!/usr/bin/env python3
import argparse
import csv
import datetime as dt
import glob
import multiprocessing as mp
import os
import shutil
import signal
import statistics
import time
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable, List

import whisper
from whisper.tokenizer import LANGUAGES

MODEL = None
LANGUAGE = None


def _init_worker(model_name: str, language: str) -> None:
    global MODEL, LANGUAGE
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    warnings.filterwarnings(
        "ignore",
        message="FP16 is not supported on CPU; using FP32 instead",
    )
    warnings.filterwarnings(
        "ignore",
        message="resource_tracker: There appear to be .* leaked semaphore objects",
    )
    LANGUAGE = language
    MODEL = whisper.load_model(model_name)


def _transcribe_one(audio_path_str: str, overwrite: bool) -> tuple[str, str, float]:
    audio_path = Path(audio_path_str)
    output_path = audio_path.with_suffix(".txt")
    if output_path.exists() and not overwrite:
        return ("skipped", str(output_path), 0.0)
    start = time.perf_counter()
    result = MODEL.transcribe(str(audio_path), language=LANGUAGE)
    temp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    temp_path.write_text(_format_transcript(result, audio_path), encoding="utf-8")
    temp_path.replace(output_path)
    _copy_file_times(audio_path, output_path)
    elapsed = time.perf_counter() - start
    return ("ok", str(output_path), elapsed)


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
    files: List[Path],
    model_name: str,
    language: str,
    overwrite: bool,
    workers: int,
    metrics_path: Path | None,
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

    target_files = [path for path in files if not path.is_dir()]
    total = len(target_files)
    processed = 0
    skipped = 0
    durations: List[float] = []
    start_total = time.perf_counter()

    if overwrite:
        to_process = target_files
    else:
        to_process = []
        for audio_path in target_files:
            output_path = audio_path.with_suffix(".txt")
            if output_path.exists():
                skipped += 1
                print(f"PULADO (já existe): {output_path}")
            else:
                to_process.append(audio_path)

    if workers <= 1:
        model = whisper.load_model(model_name)
        try:
            for audio_path in to_process:
                output_path = audio_path.with_suffix(".txt")
                start = time.perf_counter()
                result = model.transcribe(
                    str(audio_path), language=normalized_language
                )
                temp_path = output_path.with_suffix(output_path.suffix + ".tmp")
                temp_path.write_text(
                    _format_transcript(result, audio_path), encoding="utf-8"
                )
                temp_path.replace(output_path)
                _copy_file_times(audio_path, output_path)
                duration = time.perf_counter() - start
                durations.append(duration)
                _append_metrics(
                    metrics_path, audio_path, output_path, duration, workers
                )
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
        _print_performance_summary(start_total, total, processed, skipped, durations)
        return

    ctx = mp.get_context("spawn")
    executor = ProcessPoolExecutor(
        max_workers=workers,
        initializer=_init_worker,
        initargs=(model_name, normalized_language),
        mp_context=ctx,
    )
    try:
        future_map = {
            executor.submit(_transcribe_one, str(path), overwrite): path
            for path in to_process
        }
        for future in as_completed(future_map):
            result = future.result()
            status = result[0]
            output_path = result[1]
            if status == "skipped":
                skipped += 1
                print(f"PULADO (já existe): {output_path}")
            else:
                duration = result[2]
                durations.append(duration)
                _append_metrics(
                    metrics_path,
                    Path(future_map[future]),
                    Path(output_path),
                    duration,
                    workers,
                )
                processed += 1
                print(f"OK: {output_path}")
    except KeyboardInterrupt:
        executor.shutdown(wait=False, cancel_futures=True)
        for child in mp.active_children():
            child.terminate()
        for child in mp.active_children():
            child.join(timeout=1)
        remaining = total - processed - skipped
        print("\nInterrompido pelo usuário (Ctrl+C).")
        print(f"Total de arquivos: {total}")
        print(f"Processados: {processed}")
        print(f"Pulados (já existiam): {skipped}")
        print(f"Restantes: {remaining}")
        return
    finally:
        executor.shutdown(wait=True, cancel_futures=False)
    _print_performance_summary(start_total, total, processed, skipped, durations)


def _print_performance_summary(
    start_total: float,
    total: int,
    processed: int,
    skipped: int,
    durations: List[float],
) -> None:
    elapsed_total = time.perf_counter() - start_total
    print("\nResumo de desempenho")
    print(f"Total de arquivos: {total}")
    print(f"Processados: {processed}")
    print(f"Pulados (já existiam): {skipped}")
    print(f"Tempo total: {elapsed_total:.2f}s")
    if durations:
        print(f"Tempo médio por arquivo: {statistics.mean(durations):.2f}s")
        print(f"Mediana por arquivo: {statistics.median(durations):.2f}s")
        print(f"Mínimo por arquivo: {min(durations):.2f}s")
        print(f"Máximo por arquivo: {max(durations):.2f}s")


def _format_transcript(result: dict, audio_path: Path) -> str:
    segments = result.get("segments") or []
    if not segments:
        return result.get("text", "").strip() + "\n"
    base_time = dt.datetime.fromtimestamp(audio_path.stat().st_mtime)
    lines = []
    for segment in segments:
        start = float(segment.get("start", 0.0))
        text = (segment.get("text") or "").strip()
        timestamp = _format_timestamp_with_date(base_time, start)
        lines.append(f"{timestamp}\t{text}")
    return "\n".join(lines).strip() + "\n"


def _format_timestamp_with_date(base_time: dt.datetime, seconds: float) -> str:
    delta = dt.timedelta(seconds=seconds)
    ts = base_time + delta
    return ts.strftime("%d/%m/%Y %H:%M:%S.%f")[:-3]


def _copy_file_times(source: Path, target: Path) -> None:
    try:
        shutil.copystat(source, target)
    except OSError:
        stats = source.stat()
        os.utime(target, (stats.st_atime, stats.st_mtime))


def _append_metrics(
    metrics_path: Path | None,
    input_path: Path,
    output_path: Path,
    duration: float,
    workers: int,
) -> None:
    if metrics_path is None:
        return
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not metrics_path.exists()
    with metrics_path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        if write_header:
            writer.writerow(["input", "output", "duration_sec", "workers"])
        writer.writerow(
            [str(input_path), str(output_path), f"{duration:.6f}", str(workers)]
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Transcreve arquivos de áudio (.opus, .mp3, etc.) para .txt usando openai-whisper."
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="Arquivo(s) ou padrão(ões) glob, ex: ./opus/*.opus ou ./mp3/*.mp3",
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
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Quantidade de processos paralelos (>=1).",
    )
    parser.add_argument(
        "--metrics-csv",
        type=Path,
        default=None,
        help="Caminho para salvar métricas em CSV (opcional).",
    )
    args = parser.parse_args()

    files = expand_inputs(args.inputs)
    transcribe_files(
        files,
        args.model,
        args.language,
        args.overwrite,
        args.workers,
        args.metrics_csv,
    )


if __name__ == "__main__":
    main()
