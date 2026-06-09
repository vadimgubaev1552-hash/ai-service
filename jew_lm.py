import os
import json
import re
import math
from dotenv import load_dotenv
from openai import OpenAI
from duckduckgo_search import DDGS

load_dotenv()
api_key = os.getenv("OPENROUTER_API_KEY")
if not api_key:
    raise ValueError("Не найден API-ключ. Убедитесь, что файл .env содержит переменную OPENROUTER_API_KEY.")

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=api_key,
)

PRICE_PER_GRAM = {
    375: 3550,
    500: 4850,
    583: 5900,
    585: 5900,
    750: 6000,
    958: 7900
}

def calculate_weight_from_dimensions(outer_diameter_mm: float, inner_diameter_mm: float, height_mm: float, purity: int) -> float:
    density_map = {
        375: 11.5,
        500: 12.5,
        583: 13.4,
        585: 13.6,
        750: 15.5,
        958: 18.3
    }
    density = density_map.get(purity, 13.6)

    R = outer_diameter_mm / 2 / 10
    r = inner_diameter_mm / 2 / 10
    h = height_mm / 10

    volume = math.pi * (R**2 - r**2) * h
    weight = volume * density

    return round(weight, 2)

def evaluate_jewelry(item_string: str) -> str:
    parts = [p.strip() for p in item_string.split(';')]

    if len(parts) < 4:
        return "Ошибка: недостаточно параметров. Корректный формат: Тип;Проба;Вставки;Состояние;[Вес]"

    item_type = parts[0]
    purity = parts[1]
    stones = parts[2]
    condition = parts[3]

    weight = 5.0
    if len(parts) >= 5 and parts[4]:
        try:
            weight = float(parts[4].replace(',', '.'))
        except ValueError:
            weight = 5.0

    condition_lower = condition.lower()
    if "нов" in condition_lower:
        probability = "Высокая"
    elif "средн" in condition_lower:
        probability = "Средняя"
    elif "плох" in condition_lower:
        probability = "Низкая"
    else:
        probability = "Средняя"

    if stones.lower() == 'да':
        query = f"скупка золотого {item_type} {purity} пробы с камнем цена"
    else:
        query = f"скупка золотого {item_type} {purity} пробы цена"

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=3))

        snippets = "\n".join([f"- {r['title']}: {r['body']}" for r in results])

        return (
            f"АНАЛИЗ ИЗДЕЛИЯ:\n"
            f"- Тип: {item_type}\n"
            f"- Проба: {purity}\n"
            f"- Вставки: {stones}\n"
            f"- Состояние: {condition}\n"
            f"- Вес: {weight} г.\n"
            f"- Вероятность принятия: {probability}\n\n"
            f"РЕЗУЛЬТАТЫ ПОИСКА (запрос: '{query}'):\n{snippets}"
        )
    except Exception as e:
        return f"Ошибка при выполнении поиска: {str(e)}"

def evaluate_proba(item_string: str) -> str:
    parts = [p.strip() for p in item_string.split(';')]

    if len(parts) < 4:
        return "Ошибка: недостаточно параметров."

    purity = parts[1]
    condition = parts[3]

    weight = 5.0
    if len(parts) >= 5 and parts[4]:
        try:
            weight = float(parts[4].replace(',', '.'))
        except ValueError:
            weight = 5.0

    price = PRICE_PER_GRAM.get(int(purity))
    if price is None:
        return f"Ошибка: неизвестная проба '{purity}'. Допустимые значения: 375, 500, 583, 585, 750, 958."

    total_price = price * weight
    loan_amount = int(total_price * 0.6)
    buyout_amount = int(total_price * 0.85)

    condition_lower = condition.lower()
    if "нов" in condition_lower:
        probability = "Высокая"
    elif "средн" in condition_lower:
        probability = "Средняя"
    elif "плох" in condition_lower:
        probability = "Низкая"
    else:
        probability = "Средняя"

    return f"{loan_amount};{buyout_amount};{probability};None;None;None;None"

tools = [
    {
        "type": "function",
        "function": {
            "name": "evaluate_jewelry",
            "description": "Ищет актуальные цены скупки золота указанной пробы в интернете.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_string": {
                        "type": "string",
                        "description": "Строка параметров: 'Тип;Проба;Вставки;Состояние;[Вес]'. Пример: 'Кольцо;585;Нет;Среднее;10'"
                    }
                },
                "required": ["item_string"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "evaluate_proba",
            "description": "Рассчитывает стоимость изделия по фиксированному справочнику цен.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_string": {
                        "type": "string",
                        "description": "Строка параметров: 'Тип;Проба;Вставки;Состояние;[Вес]'. Пример: 'Кольцо;585;Нет;Среднее;10'"
                    }
                },
                "required": ["item_string"],
            },
        },
    },
]

AVAILABLE_TOOLS = {
    "evaluate_jewelry": evaluate_jewelry,
    "evaluate_proba": evaluate_proba,
}

SYSTEM_PROMPT = """Ты — профессиональный оценщик ювелирных изделий в ломбарде.

Алгоритм работы:
1. Прими от пользователя строку параметров изделия.
2. Вызови инструмент `evaluate_jewelry` — он выполнит поиск актуальных цен в интернете.
3. Проанализируй результаты поиска:
   - Если в сниппетах есть конкретная цена изделия или цена за грамм — используй её для расчётов.
   - Если цена за грамм указана, умножь её на вес изделия из параметров.
   - Если в результатах поиска НЕТ релевантных цен (пусто, нерелевантно, ошибка) — вызови инструмент `evaluate_proba` для расчёта по справочнику.
4. Рассчитай предварительную сумму займа как 60% (0.6) от итоговой цены. Округли до целого.
5. Выведи ответ СТРОГО в следующем формате (одной строкой, без пояснений):
{сумма_займа};{сумма_выкупа};{Вероятность};None;None;None;None

Пример:
4500;6375;Высокая;None;None;None;None

=== ДОПОЛНИТЕЛЬНЫЙ БЛОК: ОБРАБОТКА ВИЗУАЛЬНОЙ ВЕРИФИКАЦИИ ===
Если во входных данных присутствует раздел "=== ОТЧЁТ О ВИЗУАЛЬНОЙ ВЕРИФИКАЦИИ ===":
1. Проанализируй уровень критичности и список расхождений.
2. При уровне 'HIGH' — установи вероятность принятия в значение 'Низкая', игнорируя первоначальную оценку по состоянию.
3. При уровне 'LOW' — понизь вероятность на одну ступень (Высокая → Средняя, Средняя → Низкая, Низкая остаётся без изменений).
4. Если расхождений не обнаружено — используй первоначальную вероятность, рассчитанную по состоянию.
5. В итоговом ответе сохрани формат: {сумма_займа};{сумма_выкупа};{Вероятность};None;None;None;None
"""

def run_agent(user_message: str, model: str = "openai/gpt-4o-mini"):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    max_iterations = 5
    iteration = 0

    while iteration < max_iterations:
        iteration += 1
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
        )
        msg = response.choices[0].message
        messages.append(msg)

        if not msg.tool_calls:
            return msg.content

        for call in msg.tool_calls:
            fn_name = call.function.name
            if fn_name not in AVAILABLE_TOOLS:
                result = f"Ошибка: неизвестный инструмент '{fn_name}'"
            else:
                fn = AVAILABLE_TOOLS[fn_name]
                args = json.loads(call.function.arguments)
                result = fn(**args)
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": result,
            })

    return "Превышено максимальное количество итераций поиска."

def _get_first_image_string(data):
    if isinstance(data, str):
        return data.strip()
    if isinstance(data, (list, tuple)):
        for item in data:
            result = _get_first_image_string(item)
            if result:
                return result
    return None

def verify_visual_data(text_parameters: str, images_data, model: str = "openai/gpt-4o-mini") -> dict:
    image_base64 = _get_first_image_string(images_data)

    if not image_base64:
        return {"mismatches": [], "visual_analysis": {}, "severity": "none", "dimensions": {}}

    parts = [p.strip() for p in text_parameters.split(';')]
    text_type = parts[0].lower() if len(parts) > 0 else ""
    text_stones = parts[2].lower() if len(parts) > 2 else ""
    text_condition = parts[3].lower() if len(parts) > 3 else ""

    verification_prompt = """Ты — эксперт-геммолог, выполняющий верификацию ювелирного изделия.
На изображении есть банковская карта как эталон размера.
Реальные размеры карты: ширина 85.6 мм, высота 53.98 мм.

Проанализируй изображение и определи следующие характеристики.
Отвечай СТРОГО в формате JSON, без пояснений:

{
    "type": "Кольцо / Серьги / Браслет / Кулон / Цепь / Колье / Не определено",
    "has_stones": "Да / Нет",
    "condition": "Как новое / Среднее / Плохое",
    "has_defects": "Да / Нет",
    "stones_damaged": "Да / Нет",
    "outer_diameter_mm": 0,
    "inner_diameter_mm": 0,
    "height_mm": 0,
    "width_mm": 0
}

Если изделие не кольцо, укажи approximate_size_mm вместо outer_diameter_mm.
"""

    if not image_base64.startswith("data:image"):
        image_url = f"data:image/jpeg;base64,{image_base64}"
    else:
        image_url = image_base64

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": verification_prompt},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]
            }],
            max_tokens=500,
            temperature=0.0
        )
        content = response.choices[0].message.content
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if not json_match:
            return {"mismatches": ["Ошибка парсинга ответа Vision-модели"], "visual_analysis": {}, "severity": "low", "dimensions": {}}

        visual = json.loads(json_match.group())
    except Exception as e:
        return {"mismatches": [f"Ошибка визуального анализа: {str(e)}"], "visual_analysis": {}, "severity": "low", "dimensions": {}}

    mismatches = []
    severity = "none"

    visual_type = visual.get("type", "").lower()
    if text_type and visual_type and text_type not in visual_type and visual_type not in text_type:
        mismatches.append(f"КРИТИЧНО: заявлен тип '{parts[0]}', но на изображении — '{visual.get('type')}'.")
        severity = "high"

    visual_stones = visual.get("has_stones", "").lower()
    if text_stones == "нет" and visual_stones == "да":
        mismatches.append("Заявлено отсутствие вставок, но визуально обнаружены камни.")
        severity = "high" if severity != "high" else severity
    elif text_stones == "да" and visual_stones == "нет":
        mismatches.append("Заявлено наличие вставок, но визуально камни не обнаружены.")
        if severity == "none":
            severity = "low"

    visual_condition = visual.get("condition", "").lower()
    if "нов" in text_condition and "плох" in visual_condition:
        mismatches.append(f"Состояние заявлено как '{parts[3]}', но визуально — '{visual.get('condition')}'.")
        if severity == "none":
            severity = "low"

    if visual_stones == "да" and visual.get("stones_damaged", "").lower() == "да":
        mismatches.append("Визуально обнаружены повреждения вставок (сколы, трещины).")
        if severity == "none":
            severity = "low"

    if visual.get("has_defects", "").lower() == "да":
        mismatches.append("Визуально обнаружены дефекты изделия.")
        if severity == "none":
            severity = "low"

    dimensions = {
        "outer_diameter_mm": visual.get("outer_diameter_mm", 0),
        "inner_diameter_mm": visual.get("inner_diameter_mm", 0),
        "height_mm": visual.get("height_mm", 0),
        "width_mm": visual.get("width_mm", 0)
    }

    return {
        "mismatches": mismatches,
        "visual_analysis": visual,
        "severity": severity,
        "dimensions": dimensions
    }

def integrate_verification_report(result_string: str, images_data) -> tuple:
    if not images_data:
        return result_string, {}

    verification = verify_visual_data(result_string, images_data)
    mismatches = verification["mismatches"]
    severity = verification["severity"]
    dimensions = verification["dimensions"]

    if not mismatches:
        return result_string + "\n\n=== ВИЗУАЛЬНАЯ ВЕРИФИКАЦИЯ ===\nРасхождений не обнаружено. Данные достоверны.", dimensions

    report = "\n\n=== ОТЧЁТ О ВИЗУАЛЬНОЙ ВЕРИФИКАЦИИ ===\n"
    report += f"Уровень критичности: {severity.upper()}\n"
    report += "Обнаруженные расхождения:\n"
    for i, mismatch in enumerate(mismatches, 1):
        report += f"  {i}. {mismatch}\n"

    if severity == "high":
        report += (
            "\nТРЕБОВАНИЕ: В связи с существенными расхождениями между "
            "декларативными и визуальными данными, СНИЗИТЬ вероятность "
            "принятия до 'Низкая' независимо от состояния изделия.\n"
        )
    elif severity == "low":
        report += (
            "\nТРЕБОВАНИЕ: В связи с обнаруженными несоответствиями, "
            "СНИЗИТЬ вероятность принятия на одну ступень "
            "(Высокая → Средняя, Средняя → Низкая).\n"
        )

    return result_string + report, dimensions