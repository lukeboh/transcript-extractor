# Transcript Extractor

Projeto para transcrição em lote de áudio (opus/mp3/etc.), concatenação de transcrições e ajuste de datas dos arquivos com base no nome.

## Requisitos

- Python 3.12+
- `ffmpeg` disponível no `PATH`

## Ambiente virtual (.venv)

Preparar, instalar dependências e ativar:

```bash
python3 -m venv ./.venv
source ./.venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements.txt
```

Para sair do ambiente:

```bash
deactivate
```

Instalação de dependências:

```bash
python3 -m venv ./.venv
source ./.venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements.txt
```

## Script de transcrição

Arquivo: [`transcribe.py`](transcribe.py:1)

Transcreve arquivos de áudio para `.txt` mantendo o mesmo nome base. Suporta glob patterns.

### Sintaxe

```bash
python3 transcribe.py <inputs...> [--model MODELO] [--language IDIOMA] [--overwrite] [--workers N] [--metrics-csv ARQUIVO]
```

### Parâmetros

- `<inputs...>`: arquivo(s) ou padrões glob (ex.: `./opus/*.opus`, `./mp3/*.mp3`)
- `--model`: modelo Whisper (`tiny`, `base`, `small`, `medium`, `large`)
- `--language`: idioma (ex.: `pt`)
- `--overwrite`: sobrescreve `.txt` existentes
- `--workers`: quantidade de processos paralelos
- `--metrics-csv`: salva métricas por arquivo em CSV

### Formato de saída

Cada linha do `.txt` contém data/hora base do arquivo + offset do segmento:

```
DD/MM/AAAA HH:MM:SS.mmm<TAB>texto
```

O `.txt` herda as datas do arquivo de origem.

### Exemplos

Transcrever todos os `.opus` de uma pasta:

```bash
python3 transcribe.py ./opus/*.opus --model small --language pt
```

Transcrever um `.mp3` específico:

```bash
python3 transcribe.py "./mp3/2021-02-10 13 11 05 - Gina de Oliveira Mendonça - Audio Message.mp3" --model small --language pt
```

Gerar métricas em CSV e usar 4 processos:

```bash
python3 transcribe.py ./opus/*.opus --metrics-csv metrics.csv --workers 4
```

## Concatenar transcrições

Arquivo: [`concat_transcripts.py`](concat_transcripts.py:1)

Concatena `.txt` em ordem cronológica (mtime), adicionando o nome do arquivo antes do conteúdo e uma linha em branco entre arquivos.

### Sintaxe

```bash
python3 concat_transcripts.py --input-dir ./opus --output ./transcricoes_concatenadas.txt
```

## Ajustar data dos arquivos pelo nome

Arquivo: [`fix_mtime_from_name.py`](fix_mtime_from_name.py:1)

Atualiza `mtime`/`atime` com base no prefixo do nome no formato `YYYY-MM-DD HH mm ss`.

### Sintaxe

```bash
python3 fix_mtime_from_name.py ./mp3/*.mp3
```

## Observações

- O `ffmpeg` é obrigatório para leitura dos áudios.
- Para interromper o processamento, use `Ctrl+C`.
