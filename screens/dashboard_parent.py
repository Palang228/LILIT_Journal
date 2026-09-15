"""экран родителя."""
import flet as ft
from models.user import app_state
from services.supabase_client import supabase
from components.navbar import BottomNavBar


class ParentDashboard(ft.View):
    def __init__(self, page: ft.Page, on_navigate):
        super().__init__(route="/parent")
        self.page = page
        self.on_navigate = on_navigate
        self.user = app_state.current_user
        self.build_ui()

    def build_ui(self):
        greeting = ft.Text(f"Здравствуйте, {self.user.full_name}! 👨‍👩‍👧", size=24, weight=ft.FontWeight.BOLD)
        children_card = ft.Card(content=ft.Container(content=ft.Column([
            ft.Text("👶 Мои дети", size=16, weight=ft.FontWeight.BOLD), self._build_children()
        ], spacing=0), padding=15), elevation=2)
        notifications = ft.Card(content=ft.Container(content=ft.Column([
            ft.Text("🔔 Уведомления", size=16, weight=ft.FontWeight.BOLD), self._build_notifications()
        ], spacing=0), padding=15), elevation=2)
        main = ft.Container(content=ft.Column([
            greeting, ft.Divider(), children_card, ft.Divider(), notifications
        ], spacing=15, scroll=ft.ScrollMode.AUTO), padding=20, expand=True)
        self.controls = [
            ft.Column([main, BottomNavBar(self.page, self.on_navigate, active_tab="home")], expand=True, spacing=0)
        ]

    def _build_children(self):
        try:
            children = supabase.get_children(self.user.user_id).data or []
            if not children:
                return ft.Text("Нет привязанных детей", color=ft.colors.ON_SURFACE_VARIANT)
            from concurrent.futures import ThreadPoolExecutor
            def child_row(child):
                name = child.get("full_name", "Ребёнок")
                class_name = child.get("class_name", "")
                try:
                    marks = supabase.get_marks(student_id=child.get("id")).data or []
                except Exception:
                    marks = []
                avg = sum(float(m.get("value", 0)) for m in marks) / len(marks) if marks else 0
                return ft.ListTile(
                    leading=ft.CircleAvatar(content=ft.Text(name[0].upper())),
                    title=ft.Text(name),
                    subtitle=ft.Text(f"{class_name} класс • Средний балл: {avg:.1f}"),
                )
            with ThreadPoolExecutor(max_workers=min(6, max(1, len(children)))) as pool:
                items = list(pool.map(child_row, children))
            return ft.Column(items, spacing=0)
        except Exception as e:
            return ft.Text(f"Ошибка: {str(e)}", color=ft.colors.RED)

    def _build_notifications(self):
        try:
            notifs = supabase.get_notifications(self.user.user_id).data or []
            if not notifs:
                return ft.Text("Нет новых уведомлений", color=ft.colors.ON_SURFACE_VARIANT)
            items = []
            for n in notifs[:5]:
                is_read = n.get("is_read", False)
                items.append(ft.ListTile(
                    leading=ft.Icon(ft.icons.CHECK_CIRCLE if is_read else ft.icons.WARNING,
                                    color=ft.colors.GREEN if is_read else ft.colors.ORANGE, size=20),
                    title=ft.Text(n.get("message", ""), size=13),
                ))
            return ft.Column(items, spacing=0)
        except Exception:
            return ft.Text("Ошибка загрузки", color=ft.colors.ON_SURFACE_VARIANT)

    def logout(self, e=None):
        try:
            supabase.sign_out()
        except Exception:
            pass
        app_state.clear()
        supabase.clear_saved_session()
        self.page.go("/login")
