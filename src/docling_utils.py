"""
Docling document extraction utility.

WARNING: Функция не закончена! Требует доработки для универсальной поддержки всех форматов.
TODO: Добавить отдельную поддержку изображений (image extraction/vision).
"""
import pprint
from docling.document_converter import DocumentConverter
import logging

DISCORD_LIMIT = 1800

def extract_docling_content(temp_path):
    """
    Извлекает текст и таблицы из документа через Docling.
    WARNING: Функция не закончена! Требует доработки для универсальной поддержки всех форматов.
    TODO: Добавить отдельную поддержку изображений (image extraction/vision).

    :param temp_path: путь к временному файлу
    :return: tuple (text, table_chunks, structured)
    table_chunks — список строк, каждая <= DISCORD_LIMIT символов
    """
    converter = DocumentConverter()
    result = converter.convert(temp_path)
    structured = result.document.model_dump()
    # Логируем структуру для отладки
    logging.info(f"[Docling] structured (full):\n{pprint.pformat(structured)[:2000]}")
    # Извлекаем текст
    try:
        text = "\n".join(
            s if isinstance(s, str) else getattr(s, 'text', str(s))
            for s in result.document.texts
        )
    except Exception as e:
        text = ""
        logging.error(f"[Docling] Ошибка при извлечении текста: {e}")
    # Извлекаем таблицы (только с реальными данными) и разбиваем на chunk'и
    def extract_table_chunks(structured):
        table_chunks = []
        def walk(obj, parent_key=None, sheet_name=None):
            if isinstance(obj, dict):
                local_sheet = sheet_name
                if 'name' in obj and obj['name']:
                    local_sheet = obj['name']
                for k, v in obj.items():
                    if k == 'data' and isinstance(v, list) and v and isinstance(v[0], dict):
                        headers = v[0].keys()
                        rows = [list(map(str, row.values())) for row in v]
                        non_empty_rows = [row for row in rows if any(cell.strip() for cell in row)]
                        if not non_empty_rows:
                            continue
                        table_title = f"**{local_sheet or parent_key or 'Таблица'}**"
                        table_md = '| ' + ' | '.join(headers) + ' |\n'
                        table_md += '| ' + ' | '.join(['---'] * len(headers)) + ' |\n'
                        for row in non_empty_rows:
                            table_md += '| ' + ' | '.join(row) + ' |\n'
                        # Разбиваем на chunk'и по DISCORD_LIMIT
                        lines = [line for line in table_md.split('\n') if line.strip()]
                        chunk = [table_title]
                        chunk_len = len(table_title)
                        for line in lines:
                            if chunk_len + len(line) + 1 > DISCORD_LIMIT:
                                table_chunks.append('\n'.join(chunk))
                                chunk = [line]
                                chunk_len = len(line)
                            else:
                                chunk.append(line)
                                chunk_len += len(line) + 1
                        if chunk:
                            table_chunks.append('\n'.join(chunk))
                    else:
                        walk(v, k, local_sheet)
            elif isinstance(obj, list):
                for item in obj:
                    walk(item, parent_key, sheet_name)
        walk(structured)
        return table_chunks
    table_chunks = extract_table_chunks(structured)
    return text, table_chunks, structured
