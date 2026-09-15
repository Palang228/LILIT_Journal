"""Экран прохождения теста учеником."""
import flet as ft
from models.user import app_state
from services.supabase_client import supabase
from components.topbar import TopBar


class HomeworkTestScreen(ft.View):
    def __init__(self, page, on_navigate):
        super().__init__(route="/homework_test")
        self.page = page
        self.on_navigate = on_navigate
        self.user = app_state.current_user
        self.answers = {}
        self.questions = []
        self.homework = None
        self.build_ui()

    def build_ui(self):
        hid = app_state.selected_homework_id
        if not hid:
            self.controls = [TopBar("Тест"), ft.Text("Тест не выбран.")]
            return
        try:
            self.homework = supabase.get_homework(hid).data or {}
            self.questions = self.homework.get("test_questions") or []
        except Exception as ex:
            self.controls = [TopBar("Тест"), ft.Text(f"Ошибка: {ex}", color=ft.colors.RED)]
            return

        self.message = ft.Text("")
        controls = [ft.Text(self.homework.get("topic") or "Тест", size=22, weight=ft.FontWeight.BOLD)]
        if self.homework.get("source_text"):
            controls.append(ft.Text("Тест создан по загруженному учителем тексту параграфа.", size=12,
                                    color=ft.colors.ON_SURFACE_VARIANT))
        for i, q in enumerate(self.questions):
            options = q.get("options") or []
            rg = ft.RadioGroup(
                content=ft.Column([
                    ft.Radio(value=str(j), label=str(opt)) for j, opt in enumerate(options)
                ]),
                on_change=lambda e, idx=i: self.answers.__setitem__(idx, e.control.value),
            )
            controls.append(ft.Card(content=ft.Container(content=ft.Column([
                ft.Text(f"{i + 1}. {q.get('question', '')}", weight=ft.FontWeight.BOLD), rg
            ]), padding=12)))

        if not self.questions:
            controls.append(ft.Text("В этом задании нет вопросов теста."))
        else:
            controls.extend([
                ft.ElevatedButton("Завершить тест", icon=ft.icons.SEND, on_click=self.submit),
                self.message,
            ])

        self.controls = [
            TopBar("Ответить на тест", leading=ft.IconButton(ft.icons.ARROW_BACK, tooltip="Назад", on_click=lambda e: self.page.go("/schedule"))),
            ft.Container(content=ft.Column(controls, scroll=ft.ScrollMode.AUTO, spacing=12), padding=15, expand=True),
        ]

    def submit(self, e):
        if not self.questions:
            return
        if len(self.answers) < len(self.questions):
            self.message.value = "Ответьте на все вопросы."
            self.page.update()
            return
        try:
            answers = []
            correct = 0
            for i, q in enumerate(self.questions):
                selected = int(self.answers.get(i, -1))
                expected = int(q.get("correct_index", 0))
                if selected == expected:
                    correct += 1
                answers.append({"question_index": i, "selected_index": selected})
            score = round(correct * 100 / len(self.questions))
            supabase.submit_homework({
                "homework_id": self.homework["id"],
                "student_id": self.user.user_id,
                "is_completed": True,
                "status": "submitted",
                "test_answers": answers,
                "test_score": score,
            })
            try:
                supabase.add_xp({"student_id": self.user.user_id, "xp_amount": max(5, score // 10),
                                 "reason": "Тест выполнен вовремя"})
            except Exception:
                pass
            self.message.value = f"Тест отправлен ✅ Результат: {score}%"
            self.page.update()
        except Exception as ex:
            self.message.value = f"Ошибка отправки: {ex}"
            self.page.update()
