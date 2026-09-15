"""Профиль пользователя"""
import flet as ft
from models.user import app_state
from services.supabase_client import supabase
from components.navbar import BottomNavBar
from components.topbar import TopBar


class ProfileScreen(ft.View):
    def __init__(self, page, on_navigate):
        super().__init__(route="/profile")
        self.page = page
        self.on_navigate = on_navigate
        self.user = app_state.current_user
        self.build_ui()

    def build_ui(self):
        name = self.user.full_name or "Пользователь"
        self.avatar = ft.CircleAvatar(content=ft.Text(name[0].upper(), size=36), radius=48)
        self.name_field = ft.TextField(label="ФИО", value=name, width=360)
        self.phone_field = ft.TextField(label="Телефон", value=self.user.phone or "", width=360)
        self.email_field = ft.TextField(label="Email", value=self.user.email, width=360, read_only=True)
        class_value = supabase.infer_test_class(self.user.email, self.user.class_name) or "Не назначен"
        self.class_field = ft.TextField(label="Класс", value=class_value, width=360, read_only=True)
        self.role_field = ft.TextField(label="Роль", value=self.user.role, width=360, read_only=True)
        self.message = ft.Text("")
        info = ft.Card(content=ft.Container(content=ft.Column([
            self.name_field, self.phone_field, self.email_field, self.role_field, self.class_field,
            ft.ElevatedButton("Сохранить изменения", icon=ft.icons.SAVE, on_click=self.save),
            self.message,
            ft.ElevatedButton("Сменить аккаунт", icon=ft.icons.SWITCH_ACCOUNT, on_click=lambda e: self.switch_account()),
            ft.OutlinedButton("Выйти", icon=ft.icons.LOGOUT, on_click=self.logout),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10), padding=18))
        self.controls = [
            ft.Column([
                TopBar("Профиль"),
                ft.Container(content=ft.Column([self.avatar, info], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                                spacing=14, scroll=ft.ScrollMode.AUTO), padding=20, expand=True),
                BottomNavBar(self.page, self.on_navigate, active_tab="profile"),
            ], expand=True, spacing=0)
        ]

    def save(self, e):
        try:
            full_name = self.name_field.value.strip() or "Пользователь"
            phone = self.phone_field.value.strip() or None
            supabase.update_profile(self.user.user_id, {"full_name": full_name, "phone": phone})
            self.user.full_name = full_name
            self.user.phone = phone
            self.avatar.content = ft.Text(full_name[0].upper(), size=36)
            self.message.value = "Профиль сохранён ✅"
        except Exception as ex:
            self.message.value = f"Ошибка: {ex}"
        self.page.update()

    def switch_account(self):
        try:
            supabase.sign_out()
        except Exception:
            pass
        app_state.clear()
        supabase.clear_saved_session()
        self.page.go("/login")

    def logout(self, e):
        self.switch_account()
