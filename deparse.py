import json
from typing import Any, Dict


def parse_to_json_structure(input_string: str, none_as_string: bool = False) -> str:
    """
    Преобразует строку с разделителями ';' в структурированный JSON-объект.

    :param input_string: Входная строка вида "4500;7500;Высокая;None;None;None;None".
    :param none_as_string: Если True, значение "None" сохраняется как строка "None".
                           Если False (рекомендуется), конвертируется в JSON null.
    :return: Валидная строка в формате JSON.
    """
    # 1. Токенизация строки и удаление возможных лишних пробелов по краям
    parts = [part.strip() for part in input_string.split(';')]

    if len(parts) != 7:
        raise ValueError(
            f"Нарушение структуры данных: ожидается 7 элементов, получено {len(parts)}."
        )

    # 2. Строгая типизация числовых полей
    try:
        loan_amount = int(parts[0])
        buyout_amount = int(parts[1])
    except ValueError as e:
        raise ValueError(
            "Первые два поля (loanAmount и buyoutAmount) должны быть целыми числами."
        ) from e

    # 3. Вспомогательная функция для корректной обработки пустых значений
    def normalize_value(val: str) -> Any:
        if val == "None" and not none_as_string:
            return None  # При сериализации в JSON станет литералом null
        return val

    # 4. Формирование словаря (Python-представление JSON)
    result_payload: Dict[str, Any] = {
        "success": True,
        "result": {
            "loanAmount": loan_amount,
            "buyoutAmount": buyout_amount,
            "probability": normalize_value(parts[2]),
            "defects": normalize_value(parts[3]),
            "type": normalize_value(parts[4]),
            "hasStones": normalize_value(parts[5]),
            "condition": normalize_value(parts[6])
        }
    }

    # 5. Сериализация в JSON-строку
    # ensure_ascii=False необходим для корректного отображения кириллицы (например, "Высокая")
    # indent=4 обеспечивает человеко-читаемое форматирование
    return json.dumps(result_payload, ensure_ascii=False, indent=4)