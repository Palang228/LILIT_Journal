"""Отправка обычного домашнего задания фотографиями."""
import base64
import uuid
import flet as ft
from models.user import app_state
from services.supabase_client import supabase
from components.topbar import TopBar


class HomeworkSubmitScreen(ft.View):
    def __init__(self, page, on_navigate):
        super().__init__(route="/homework_submit")
        self.page = page
        self.on_navigate = on_navigate
        self.user = app_state.current_user
        self.homework = None
        self.files = []
        self.preview = ft.Column(spacing=6)
        self.file_picker = ft.FilePicker(on_result=self.on_files_picked)
        self.page.overlay.append(self.file_picker)
        self.build_ui()

    def build_ui(self):
        try:
            hid = app_state.selected_homework_id
            self.homework = supabase.get_homework(hid).data or {} if hid else None
        except Exception:
            self.homework = None
        title = (self.homework or {}).get("topic") or "Домашнее задание"
        self.message = ft.Text("")
        self.controls = [
            TopBar("Отправка ДЗ", leading=ft.IconButton(ft.icons.ARROW_BACK, tooltip="Назад", on_click=lambda e: self.page.go("/schedule"))),
            ft.Container(content=ft.Column([
                ft.Text(title, size=21, weight=ft.FontWeight.BOLD),
                ft.Text((self.homework or {}).get("exercise") or "", size=14),
                ft.ElevatedButton("Выбрать фотографии", icon=ft.icons.CAMERA_ALT,
                                  on_click=lambda e: self.file_picker.pick_files(
                                      allow_multiple=True, file_type=ft.FilePickerFileType.IMAGE)),
                self.preview,
                ft.ElevatedButton("Отправить", icon=ft.icons.SEND, on_click=self.submit),
                self.message,
            ], spacing=12, scroll=ft.ScrollMode.AUTO), padding=15, expand=True)
        ]

    def on_files_picked(self, e):
        self.files = list(e.files or [])
        self.preview.controls.clear()
        for f in self.files:
            self.preview.controls.append(ft.Text(f"✓ {f.name}"))
        self.page.update()

    def submit(self, e):
        if not self.homework:
            self.message.value = "Задание не найдено."
            self.page.update()
            return
        if not self.files:
            self.message.value = "Выберите хотя бы одну фотографию."
            self.page.update()
            return
        try:
            urls = []
            first_url = None
            for f in self.files:
                with open(f.path, "rb") as fp:
                    data = fp.read()
                path = f"submissions/{self.user.user_id}/{self.homework['id']}/{uuid.uuid4().hex}.jpg"
                supabase.upload_file("homeworks", path, data, "image/jpeg")
                url = supabase.get_public_url("homeworks", path)
                urls.append(url)
                first_url = first_url or url
            supabase.submit_homework({
                "homework_id": self.homework["id"],
                "student_id": self.user.user_id,
                "photo_url": first_url,
                "photo_urls": urls,
                "is_completed": True,
                "status": "submitted",
            })
            try:
                supabase.add_xp({"student_id": self.user.user_id, "xp_amount": 10,
                                 "reason": "Домашнее задание отправлено"})
            except Exception:
                pass
            self.message.value = "Работа отправлена ✅"
            self.page.update()
        except Exception as ex:
            self.message.value = f"Ошибка отправки: {ex}"
            self.page.update()
