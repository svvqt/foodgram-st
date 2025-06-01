import json

# Путь к исходному файлу
input_path = '../data/ingredients.json'  
# Путь для сохранения преобразованного файла
output_path = 'recipes/fixtures/ingredients.json'  

# Чтение исходного файла
with open(input_path, 'r', encoding='utf-8') as f:
    original_data = json.load(f)

# Преобразование в формат Django
converted_data = [
    {
        "model": "recipes.ingredient",  # Нужное приложение
        "pk": idx + 1,                  # Автонумерация (начинается с 1)
        "fields": {                     # Все поля переносятся сюда
            "name": item["name"],
            "measurement_unit": item["measurement_unit"]
        }
    }
    for idx, item in enumerate(original_data)
]

# Сохранение нового файла
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(converted_data, f, ensure_ascii=False, indent=2)

print(f"Файл преобразован и сохранён как: {output_path}")