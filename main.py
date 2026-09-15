"""Точка входа Лилит."""
import flet as ft
from config import APP_NAME, APP_VERSION
from models.user import app_state, UserSession
from services.supabase_client import supabase
from screens.login import LoginScreen
from screens.dashboard_student import StudentDashboard
from screens.dashboard_teacher import TeacherDashboard
from screens.dashboard_parent import ParentDashboard
from screens.dashboard_admin import AdminDashboard
from screens.schedule import ScheduleScreen
from screens.grades import GradesScreen
from screens.ai_tutor import AITutorScreen
from screens.ai_homework_checker import AIHomeworkChecker
from screens.leaderboard import LeaderboardScreen
from screens.profile import ProfileScreen
from screens.homework import HomeworkScreen
from screens.homework_test import HomeworkTestScreen
from screens.homework_submit import HomeworkSubmitScreen
from screens.homework_text import HomeworkTextScreen
from screens.teacher_class import TeacherClassScreen


class LilitApp:
    def __init__(self, page):
        self.page = page
        page.title = f"{APP_NAME} v{APP_VERSION}"
        page.theme_mode = ft.ThemeMode.LIGHT
        page.theme = ft.Theme(color_scheme_seed=ft.colors.DEEP_PURPLE, use_material3=True)
        page.padding = 0
        page.window_width = 1000
        page.window_height = 760
        page.window_min_width = 360
        page.window_min_height = 640
        app_state.page = page
        page.on_route_change = self.on_route_change
        page.on_view_pop = self.on_view_pop
        # Сразу открываем последний профиль из локального кэша.
        saved = supabase.get_saved_session() if "supabase" in globals() else None
        if saved and saved.get("profile", {}).get("role"):
            profile = dict(saved["profile"])
            if profile.get("role") == "student":
                profile["class_name"] = supabase.infer_test_class(profile.get("email"), profile.get("class_name"))
            app_state.set_user(UserSession(
                user_id=profile.get("id"), email=profile.get("email", ""),
                full_name=profile.get("full_name", "Пользователь"), role=profile.get("role", "student"),
                class_name=profile.get("class_name"), subject_id=profile.get("subject_id"),
                parent_id=profile.get("parent_id"), avatar_url=profile.get("avatar_url"),
                phone=profile.get("phone"), metadata=profile
            ))
            page.go({"student":"/schedule","teacher":"/teacher","parent":"/parent","admin":"/admin"}.get(profile.get("role"), "/login"))
            page.run_task(self._refresh_saved_session)
        else:
            page.go("/login")

    async def _refresh_saved_session(self):
        try:
            saved = supabase.get_saved_session()
            if not saved or not saved.get("refresh_token"):
                return
            import asyncio
            response = await asyncio.to_thread(
                supabase.restore_session, saved.get("access_token", ""), saved.get("refresh_token")
            )
            session = getattr(response, "session", None) or response
            profile = saved.get("profile") or {}
            if profile.get("id"):
                fresh_profile = await asyncio.to_thread(supabase.refresh_profile, profile.get("id"))
                if fresh_profile:
                    profile = {**profile, **fresh_profile}
                    if profile.get("role") == "student":
                        profile["class_name"] = supabase.infer_test_class(profile.get("email"), profile.get("class_name"))
                    app_state.set_user(UserSession(
                        user_id=profile.get("id"), email=profile.get("email", ""),
                        full_name=profile.get("full_name", "Пользователь"), role=profile.get("role", "student"),
                        class_name=profile.get("class_name"), subject_id=profile.get("subject_id"),
                        parent_id=profile.get("parent_id"), avatar_url=profile.get("avatar_url"),
                        phone=profile.get("phone"), metadata=profile
                    ))
                
            if session and profile:
                supabase.save_session(session, profile)
        except Exception:
            # Оставляем локальный кэш доступным даже при временном отсутствии сети.
            pass

    def _allowed(self, role, route):
        if not app_state.current_user:
            return route == "/login"
        if route.startswith("/admin"):
            return role == "admin"
        if route.startswith("/teacher"):
            return role == "teacher"
        if route.startswith("/parent"):
            return role == "parent"
        if route in ("/homework_test", "/homework_submit", "/homework_text"):
            return role == "student"
        return True

    def on_route_change(self, e):
        route = e.route
        if route != "/login" and not app_state.current_user:
            self.page.go("/login")
            return
        role = app_state.current_user.role if app_state.current_user else None
        if not self._allowed(role, route):
            self.page.go({"student": "/schedule", "teacher": "/teacher", "parent": "/parent", "admin": "/admin"}.get(role, "/login"))
            return
        self.page.views.clear()
        screens = {
            "/login": lambda: LoginScreen(self.page, self.on_login_success),
            "/student": lambda: StudentDashboard(self.page, self.on_navigate),
            "/teacher": lambda: TeacherDashboard(self.page, self.on_navigate),
            "/teacher_class": lambda: TeacherClassScreen(self.page, self.on_navigate),
            "/parent": lambda: ParentDashboard(self.page, self.on_navigate),
            "/admin": lambda: AdminDashboard(self.page, self.on_navigate),
            "/schedule": lambda: ScheduleScreen(self.page, self.on_navigate),
            "/grades": lambda: GradesScreen(self.page, self.on_navigate),
            "/ai_tutor": lambda: AITutorScreen(self.page, self.on_navigate),
            "/ai_homework": lambda: AIHomeworkChecker(self.page, self.on_navigate),
            "/leaderboard": lambda: LeaderboardScreen(self.page, self.on_navigate),
            "/profile": lambda: ProfileScreen(self.page, self.on_navigate),
            "/homework": lambda: HomeworkScreen(self.page, self.on_navigate),
            "/homework_test": lambda: HomeworkTestScreen(self.page, self.on_navigate),
            "/homework_submit": lambda: HomeworkSubmitScreen(self.page, self.on_navigate),
            "/homework_text": lambda: HomeworkTextScreen(self.page, self.on_navigate),
        }
        factory = screens.get(route)
        self.page.views.append(factory() if factory else LoginScreen(self.page, self.on_login_success))
        self.page.update()

    def on_view_pop(self, e):
        if len(self.page.views) > 1:
            self.page.views.pop()
            self.page.go(self.page.views[-1].route)
        else:
            self.page.go("/login")

    def on_login_success(self, role):
        self.page.go({"student": "/schedule", "teacher": "/teacher", "parent": "/parent", "admin": "/admin"}.get(role, "/schedule"))
        if app_state.current_user:
            self.page.run_task(self._warm_current_user)

    async def _warm_current_user(self):
        import asyncio
        user = app_state.current_user
        if not user:
            return
        profile = dict(user.metadata or {})
        profile.update({"id": user.user_id, "role": user.role, "class_name": user.class_name})
        await asyncio.to_thread(supabase.warm_user_cache, profile)

    def on_navigate(self, tab):
        role = app_state.current_user.role if app_state.current_user else "student"
        base = {"student": "/schedule", "teacher": "/teacher", "parent": "/parent", "admin": "/admin"}
        routes = {
            "home": base.get(role, "/schedule"), "schedule": "/schedule", "homework": "/homework",
            "grades": "/grades", "ai_tutor": "/ai_tutor", "ai_homework": "/ai_homework",
            "leaderboard": "/leaderboard", "notifications": "/parent",
            "users": "/admin", "classes": "/admin", "profile": "/profile", "teacher": "/teacher",
        }
        self.page.go(routes.get(tab, base.get(role, "/schedule")) or "/schedule")


def main(page):
    LilitApp(page)


if __name__ == "__main__":
    ft.app(target=main)
