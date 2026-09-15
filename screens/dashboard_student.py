"""Дашборд ученика"""
import flet as ft
from models.user import app_state
from services.supabase_client import supabase
from components.navbar import BottomNavBar
from components.topbar import TopBar

class StudentDashboard(ft.View):
    def __init__(self, page: ft.Page, on_navigate):
        super().__init__(route="/student")
        self.page = page
        self.on_navigate = on_navigate
        self.user = app_state.current_user
        self.homeworks_count = 0
        self.submissions_count = 0
        self.avg_mark = 0.0
        self.is_mobile = (page.width or 360) < 600
        self.load_data()
        self.build_ui()

    def load_data(self):
        try:
            if not self.user.class_name:
                try:
                    profile = supabase.refresh_profile(self.user.user_id) or {}
                    if profile.get("class_name"):
                        self.user.class_name = profile.get("class_name")
                        self.user.metadata = profile
                    else:
                        import re
                        local = str(self.user.email or "").split("@", 1)[0].lower()
                        m = re.fullmatch(r"student(\d+)", local)
                        if m:
                            grade = 5 if int(m.group(1)) == 4 else int(m.group(1))
                            self.user.class_name = f"{grade} класс"
                    app_state.set_user(self.user)
                except Exception:
                    pass
            if self.user.class_name:
                hw_res = supabase.get_homeworks(class_name=self.user.class_name)
                self.homeworks_count = len(hw_res.data) if hasattr(hw_res, 'data') else 0
                sub_res = supabase.get_submissions(student_id=self.user.user_id)
                self.submissions_count = len(sub_res.data) if hasattr(sub_res, 'data') else 0
                marks_res = supabase.get_marks(student_id=self.user.user_id)
                marks_data = marks_res.data if hasattr(marks_res, 'data') else []
                if marks_data:
                    values = [float(m.get("value", 0)) for m in marks_data]
                    self.avg_mark = sum(values) / len(values)
        except Exception as e:
            print(f"Ошибка: {e}")

    def build_ui(self):
        greeting = ft.Text(f"Привет, {self.user.full_name}! 👋", size=24 if not self.is_mobile else 20, weight=ft.FontWeight.BOLD)

        stats_row = ft.Row(
            [
                self._stat_card("📚", "ДЗ всего", str(self.homeworks_count), ft.colors.BLUE),
                self._stat_card("✅", "Сдано", f"{self.submissions_count}", ft.colors.GREEN),
                self._stat_card("⭐", "Средний балл", f"{self.avg_mark:.1f}", ft.colors.AMBER),
            ],
            alignment=ft.MainAxisAlignment.SPACE_EVENLY,
            wrap=True,
        )

        deadlines = ft.Card(
            content=ft.Container(
                content=ft.Column(
                    [ft.Text("⏰ Ближайшие дедлайны", size=16, weight=ft.FontWeight.BOLD), self._build_deadlines()],
                    spacing=0,
                ),
                padding=15,
            ),
            elevation=2,
        )

        ai_button = ft.ElevatedButton(
            content=ft.Row([ft.Icon(ft.icons.PSYCHOLOGY, size=20), ft.Text("  Спросить AI-тьютора")]),
            style=ft.ButtonStyle(padding=ft.padding.symmetric(horizontal=30, vertical=15)),
            on_click=lambda e: self.on_navigate("ai_tutor"),
        )

        check_button = ft.ElevatedButton(
            content=ft.Row([ft.Icon(ft.icons.CAMERA_ALT, size=20), ft.Text("  Проверить ДЗ по фото")]),
            style=ft.ButtonStyle(padding=ft.padding.symmetric(horizontal=30, vertical=15)),
            on_click=lambda e: self.on_navigate("ai_homework"),
        )

        main_content = ft.Container(
            content=ft.Column(
                [greeting, ft.Divider(), stats_row, ft.Divider(), deadlines, ft.Divider(),
                 ft.Row([ai_button, check_button], alignment=ft.MainAxisAlignment.CENTER, spacing=15, wrap=True)],
                spacing=15, scroll=ft.ScrollMode.AUTO,
            ),
            padding=20 if not self.is_mobile else 10,
            expand=True,
        )

        self.controls = [
            ft.Column(
                [TopBar("Лилит — Ученик", actions=[
                    ft.IconButton(ft.icons.SWITCH_ACCOUNT, tooltip="Сменить аккаунт", on_click=self.switch_account),
                    ft.IconButton(ft.icons.LOGOUT, tooltip="Выйти", on_click=self.logout),
                ]), main_content, BottomNavBar(self.page, self.on_navigate, active_tab="schedule")],
                expand=True,
                spacing=0,
            )
        ]

    def _build_deadlines(self):
        try:
            if not self.user.class_name:
                return ft.Text("Класс не назначен", color=ft.colors.ON_SURFACE_VARIANT)
            hw_res = supabase.get_homeworks(class_name=self.user.class_name)
            homeworks = hw_res.data if hasattr(hw_res, 'data') else []
            if not homeworks:
                return ft.Text("Нет дедлайнов 🎉", color=ft.colors.ON_SURFACE_VARIANT)
            items = []
            for hw in homeworks[:3]:
                due = hw.get("due_date", "")
                title = hw.get("topic", "Без названия")
                subject = hw.get("subjects", {}).get("name", "")
                items.append(ft.ListTile(
                    leading=ft.Icon(ft.icons.WARNING, color=ft.colors.ORANGE),
                    title=ft.Text(f"{subject} — {title}"),
                    subtitle=ft.Text(f"Срок: {due}"),
                ))
            return ft.Column(items, spacing=0)
        except:
            return ft.Text("Ошибка загрузки", color=ft.colors.ON_SURFACE_VARIANT)

    def _stat_card(self, emoji, label, value, color):
        return ft.Card(
            content=ft.Container(
                content=ft.Column(
                    [ft.Text(emoji, size=30), ft.Text(value, size=22, weight=ft.FontWeight.BOLD, color=color), ft.Text(label, size=12, color=ft.colors.ON_SURFACE_VARIANT)],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=5,
                ),
                padding=15, width=100 if not self.is_mobile else 90,
            ),
            elevation=2,
        )

    def switch_account(self, e): self.page.go("/login")
    def logout(self, e):
        try: supabase.sign_out()
        except: pass
        app_state.clear()
        supabase.clear_saved_session()
        self.page.client_storage.remove("saved_accounts")
        self.page.go("/login")
