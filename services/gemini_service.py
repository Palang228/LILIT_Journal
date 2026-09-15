"""Gemini"""
import io
import json
import re
from PIL import Image
from google import genai
from config import GEMINI_API_KEY, GEMINI_MODEL


class GeminiService:
    def __init__(self):
        self.model = GEMINI_MODEL
        self.client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

    def _client(self):
        if not self.client:
            raise RuntimeError("GEMINI_API_KEY не настроен.")
        return self.client

    def _candidate_models(self):
        models = [self.model, "gemini-3.8-flash", "gemini-3.6-flash"]
        unique = []
        for name in models:
            if name and name not in unique:
                unique.append(name)
        return unique

    def _generate(self, contents):
        last_error = None
        for model_name in self._candidate_models():
            try:
                return self._client().models.generate_content(model=model_name, contents=contents)
            except Exception as exc:
                last_error = exc
                message = str(exc).upper()
                if "404" not in message and "NOT_FOUND" not in message and "NO LONGER AVAILABLE" not in message:
                    raise
        raise last_error

    @staticmethod
    def _json(text, default):
        text = (text or "").strip()
        if "```" in text:
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I | re.S).strip()
        try:
            return json.loads(text)
        except Exception:
            match = re.search(r"(\{.*\}|\[.*\])", text, re.S)
            if match:
                try:
                    return json.loads(match.group(1))
                except Exception:
                    pass
        return default

    def check_homework(self, image_bytes, subject, task_description):
        image = Image.open(io.BytesIO(image_bytes))
        prompt = f"""Ты проверяешь школьную работу по предмету {subject}.
Задание: {task_description}
Проверь фото решения: распознай текст, проверь ход решения, перечисли конкретные ошибки.
Будь доброжелательным и мотивирующим; не унижай ученика и не используй сарказм.
Верни только JSON:
{{"score":0,"ai_feedback":"...","extra_tasks":["..."],"errors_found":["..."]}}
score — целое 0..100, extra_tasks — 0..5 коротких заданий."""
        response = self._generate([prompt, image])
        result = self._json(response.text, {})
        return {
            "score": max(0, min(100, int(result.get("score", 0)))),
            "ai_feedback": str(result.get("ai_feedback", "Проверка завершена.")),
            "extra_tasks": list(result.get("extra_tasks") or []),
            "errors_found": list(result.get("errors_found") or []),
        }

    def tutor_explain(self, topic, context="", level="средний"):
        prompt = f"""Ты дружелюбный школьный репетитор.
Тема: {topic}
Контекст урока: {context}
Уровень: {level}
Объясни простыми словами, с 1–2 аналогиями и примером. Не выдумывай факты."""
        return self._generate(prompt).text

    @staticmethod
    def _validate_questions(data, count):
        if not isinstance(data, list):
            return []
        valid = []
        for q in data[:count]:
            if (
                isinstance(q, dict)
                and q.get("question")
                and isinstance(q.get("options"), list)
                and len(q["options"]) == 4
            ):
                try:
                    correct = int(q.get("correct_index", 0))
                except Exception:
                    correct = 0
                q["correct_index"] = max(0, min(3, correct))
                q["explanation"] = str(q.get("explanation", ""))
                valid.append(q)
        return valid

    def generate_test(self, topic, subject, count=15):
        count = max(5, min(20, int(count)))
        prompt = f"""Создай {count} тестовых вопросов по теме "{topic}" (предмет: {subject}).
Каждый вопрос имеет ровно 4 варианта. Только один правильный.
Верни только JSON-массив объектов:
{{"question":"...","options":["A","B","C","D"],"correct_index":0,"explanation":"..."}}
correct_index — 0..3."""
        response = self._generate(prompt)
        return self._validate_questions(self._json(response.text, []), count)

    def generate_test_from_images(self, image_bytes_list, subject, assignment_text="", count=15):
        """Распознаёт несколько страниц одного параграфа и строит тест только по материалу на фото."""
        count = max(5, min(20, int(count)))
        images = [Image.open(io.BytesIO(data)) for data in image_bytes_list]
        prompt = f"""Перед тобой фотографии всего школьного параграфа по предмету {subject}.
Дополнительное указание учителя: {assignment_text or 'подготовить проверочный тест по тексту параграфа'}.

Сначала внимательно распознай и объедини текст со всех страниц в правильном порядке.
Не добавляй факты, которых нет на фотографиях.
Затем создай {count} тестовых вопросов строго по распознанному тексту.
Каждый вопрос имеет ровно 4 варианта, только один правильный.

Верни ТОЛЬКО JSON-объект такого вида:
{{
  "source_text": "полный распознанный текст параграфа",
  "questions": [
    {{"question":"...","options":["A","B","C","D"],"correct_index":0,"explanation":"..."}}
  ]
}}
"""
        response = self._generate([prompt, *images])
        data = self._json(response.text, {})
        source_text = str(data.get("source_text", "")).strip() if isinstance(data, dict) else ""
        questions = self._validate_questions(data.get("questions", []) if isinstance(data, dict) else [], count)
        return {"source_text": source_text, "questions": questions}

    def predict_target_grade(self, current_grades, target):
        grades = [float(x) for x in current_grades if 2 <= float(x) <= 5]
        avg = sum(grades) / len(grades) if grades else 0
        target = float(target)
        progress = max(0, min(100, round((avg / target) * 100))) if target else 0
        return {
            "current_avg": round(avg, 2),
            "target": target,
            "needed_avg": target,
            "recommendations": [
                "Стабильно получай оценки не ниже целевой.",
                "Разбери ошибки в последних работах.",
            ],
            "progress_percent": progress,
        }


gemini = GeminiService()
