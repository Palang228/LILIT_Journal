"""Текстовая сдача домашнего задания."""
import flet as ft
from models.user import app_state
from services.supabase_client import supabase
from components.topbar import TopBar


class HomeworkTextScreen(ft.View):
    def __init__(self, page, on_navigate):
        super().__init__(route="/homework_text")
        self.page = page
        self.user = app_state.current_user
        hid = app_state.selected_homework_id
        self.homework = supabase.get_homework(hid).data or {} if hid else {}
        self.answer = ft.TextField(label="Ваш ответ", multiline=True, min_lines=8, max_lines=16)
        self.message = ft.Text("")
        self.controls = [
            TopBar("Ответить", leading=ft.IconButton(ft.icons.ARROW_BACK, on_click=lambda e: self.page.go("/schedule"))),
            ft.Container(content=ft.Column([
                ft.Text(self.homework.get("topic") or "Домашнее задание", size=21, weight=ft.FontWeight.BOLD),
                ft.Text(self.homework.get("exercise") or ""),
                self.answer,
                ft.ElevatedButton("Отправить", icon=ft.icons.SEND, on_click=self.submit),
                self.message,
            ], scroll=ft.ScrollMode.AUTO, spacing=12), padding=15, expand=True),
        ]

    def submit(self, e):
        if not self.answer.value.strip():
            self.message.value = "Введите ответ."
            self.page.update()
            return
        try:
            supabase.submit_homework({
                "homework_id": self.homework["id"],
                "student_id": self.user.user_id,
                "answer_text": self.answer.value.strip(),
                "is_completed": True,
                "status": "submitted",
            })
            self.message.value = "Ответ отправлен ✅"
            self.page.update()
        except Exception as ex:
            self.message.value = f"Ошибка: {ex}"
            self.page.update()
