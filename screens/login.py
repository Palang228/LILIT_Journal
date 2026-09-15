"""Авторизация без хранения паролей в локальном хранилище."""
import json
import flet as ft
from services.supabase_client import supabase
from models.user import UserSession, app_state
from components.topbar import TopBar
import asyncio

class LoginScreen(ft.View):
    def __init__(self, page, on_login_success):
        super().__init__(route="/login")
        self.page=page; self.on_login_success=on_login_success
        self.saved_accounts=json.loads(self.page.client_storage.get("saved_accounts") or "[]")
        self.build_login_ui()

    async def restore_saved_session(self):
        saved = supabase.get_saved_session()
        if not saved or not saved.get("refresh_token"):
            return False
        profile = saved.get("profile") or {}
        try:
            # Сначала открываем интерфейс по локальному профилю, затем подтверждаем
            # сессию refresh-токеном в фоне. Данные дневника уже лежат в локальном кэше.
            if profile.get("id") and profile.get("role"):
                self._set_session_from_profile(profile)
                self.on_login_success(profile.get("role"))
            await asyncio.to_thread(supabase.restore_session, saved.get("access_token", ""), saved["refresh_token"])
            auth_session = getattr(supabase.client.auth, "get_session", lambda: None)()
            session = getattr(auth_session, "session", None) or auth_session
            if session and profile.get("id"):
                supabase.save_session(session, profile)
            return True
        except Exception as ex:
            # Старый/недействительный токен удаляем, но локальные данные не трогаем.
            supabase.clear_saved_session()
            return False

    def _set_session_from_profile(self, profile):
        self_user = UserSession(
            user_id=profile.get("id"), email=profile.get("email") or "",
            full_name=profile.get("full_name", "Пользователь"), role=profile.get("role", "student"),
            class_name=profile.get("class_name"), subject_id=profile.get("subject_id"), parent_id=profile.get("parent_id"),
            avatar_url=profile.get("avatar_url"), phone=profile.get("phone"), metadata=profile
        )
        app_state.set_user(self_user)

    def build_login_ui(self):
        self.email=ft.TextField(label="📧 Email", keyboard_type=ft.KeyboardType.EMAIL, width=360)
        self.password=ft.TextField(label="🔒 Пароль", password=True, can_reveal_password=True, width=360)
        self.remember=ft.Checkbox(label="Запомнить аккаунт на этом устройстве", value=True)
        self.error_text=ft.Text("", color=ft.colors.RED_400, size=12)
        self.loading=ft.ProgressRing(visible=False,width=20,height=20)
        saved_ui=[ft.Text("Быстрый вход (пароль не хранится):",weight=ft.FontWeight.BOLD)]
        for acc in self.saved_accounts:
            saved_ui.append(ft.ListTile(
                leading=ft.CircleAvatar(content=ft.Text((acc.get("full_name") or "?")[0].upper())),
                title=ft.Text(acc.get("full_name","Пользователь")),
                subtitle=ft.Text(acc.get("email","")),
                on_click=lambda e,a=acc:self.select_account(a)
            ))
        self.controls=[TopBar("Лилит — Вход"),
            ft.Container(content=ft.Column([
                ft.Icon(ft.icons.SCHOOL,size=72,color=ft.colors.PRIMARY),
                ft.Text("Лилит",size=32,weight=ft.FontWeight.BOLD),
                ft.Text("Умная образовательная платформа",color=ft.colors.ON_SURFACE_VARIANT),
                *(saved_ui if self.saved_accounts else []),
                ft.Divider(),
                self.email,self.password,self.remember,self.error_text,
                ft.ElevatedButton("Войти",icon=ft.icons.LOGIN,width=360,on_click=self.do_login),
                ft.Row([self.loading],alignment=ft.MainAxisAlignment.CENTER)
            ],horizontal_alignment=ft.CrossAxisAlignment.CENTER,spacing=12,scroll=ft.ScrollMode.AUTO),padding=24,alignment=ft.alignment.center,expand=True)]

    def select_account(self, acc):
        self.email.value=acc.get("email",""); self.password.value=""; self.page.update()
        self.page.show_snack_bar(ft.SnackBar(ft.Text("Введите пароль для защищённого входа.")))

    def _resolve_missing_student_class(self, email, profile):
        if str(profile.get("role")) != "student":
            return profile
        profile = dict(profile)
        profile["class_name"] = supabase.infer_test_class(email, profile.get("class_name"))
        return profile

    def _session(self, auth):
        user=auth.user
        profile=(supabase.refresh_profile(user.id) or supabase.get_profile(user.id).data or {})
        profile = self._resolve_missing_student_class(user.email or self.email.value, profile)
        return UserSession(user_id=user.id,email=user.email or self.email.value,full_name=profile.get("full_name","Пользователь"),
            role=profile.get("role","student"),class_name=profile.get("class_name"),subject_id=profile.get("subject_id"),
            parent_id=profile.get("parent_id"),avatar_url=profile.get("avatar_url"),phone=profile.get("phone"),metadata=profile)

    def do_login(self,e):
        email=self.email.value.strip(); password=self.password.value
        if not email or not password:
            self.error_text.value="Введите email и пароль."; self.page.update(); return
        self.loading.visible=True; self.error_text.value=""; self.page.update()
        try:
            auth_response = supabase.sign_in(email,password)
            session=self._session(auth_response); app_state.set_user(session)
            profile_for_cache = dict(session.metadata)
            profile_for_cache["email"] = session.email
            supabase.save_session(getattr(auth_response, "session", None), profile_for_cache)
            if self.remember.value:
                accounts=[a for a in self.saved_accounts if a.get("user_id")!=session.user_id]
                accounts.append({"user_id":session.user_id,"email":session.email,"full_name":session.full_name,"role":session.role,"class_name":session.class_name})
                self.page.client_storage.set("saved_accounts",json.dumps(accounts,ensure_ascii=False))
            self.loading.visible=False; self.on_login_success(session.role)
        except Exception as ex:
            self.loading.visible=False; self.error_text.value=f"Ошибка входа: {ex}"; self.page.update()
