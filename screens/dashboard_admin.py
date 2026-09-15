"""Панель администратора."""
import flet as ft
from models.user import app_state
from services.supabase_client import supabase
from components.topbar import TopBar

class AdminDashboard(ft.View):
    def __init__(self,page,on_navigate):
        super().__init__(route="/admin"); self.page=page; self.on_navigate=on_navigate; self.user=app_state.current_user; self.build_ui()
    def build_ui(self):
        stats=[]
        for emoji,label,table in [("👥","Пользователи","profiles"),("📚","Предметы","subjects"),("📝","ДЗ","homeworks")]:
            try:
                count=supabase.admin_count(table).count
                stats.append(self._card(emoji,label,str(count)))
            except Exception: stats.append(self._card(emoji,label,"—"))
        self.controls=[TopBar("Лилит — Админ", actions=[ft.IconButton(ft.icons.LOGOUT,on_click=self.logout)]),
            ft.Container(content=ft.Column([
                ft.Text(f"Администрирование, {self.user.full_name}! ⚙️",size=24,weight=ft.FontWeight.BOLD),
                ft.Row(stats,alignment=ft.MainAxisAlignment.SPACE_EVENLY,wrap=True),
                ft.Card(content=ft.Container(content=ft.Column([
                    ft.Text("Управление пользователями",size=17,weight=ft.FontWeight.BOLD),
                    ft.ElevatedButton("Создать пользователя",icon=ft.icons.ADD,on_click=self.show_create_user),
                    ft.ElevatedButton("Открыть список пользователей",icon=ft.icons.PEOPLE,on_click=self.show_users)
                ]),padding=15))
            ],scroll=ft.ScrollMode.AUTO,spacing=15),padding=20,expand=True)]
    def _card(self,emoji,label,value):
        return ft.Card(content=ft.Container(content=ft.Column([ft.Text(emoji,size=28),ft.Text(value,size=21,weight=ft.FontWeight.BOLD),ft.Text(label,size=12)],horizontal_alignment=ft.CrossAxisAlignment.CENTER),padding=14,width=120))
    def show_create_user(self,e):
        email=ft.TextField(label="Email"); password=ft.TextField(label="Пароль",password=True); name=ft.TextField(label="ФИО")
        role=ft.Dropdown(label="Роль",options=[ft.dropdown.Option(x) for x in ["student","teacher","parent","admin"]],value="student")
        cls=ft.TextField(label="Класс (например, 9Б)", hint_text="Для ученика: 5А, 9Б, 11Б")
        def close(e): dlg.open=False; self.page.update()
        def create(e):
            try:
                auth=supabase.admin_create_user(email.value,password.value,{"full_name":name.value.strip(),"role":role.value})
                uid=auth.user.id
                supabase.admin_update_profile(uid,{"full_name":name.value.strip(),"role":role.value,"class_name":cls.value.strip() or None})
                close(e); self.page.show_snack_bar(ft.SnackBar(ft.Text("Пользователь создан.")))
            except Exception as ex: self.page.show_snack_bar(ft.SnackBar(ft.Text(f"Ошибка: {ex}")))
        dlg=ft.AlertDialog(title=ft.Text("Создать пользователя"),content=ft.Column([email,password,name,role,cls],tight=True),actions=[ft.TextButton("Отмена",on_click=close),ft.ElevatedButton("Создать",on_click=create)])
        self.page.dialog=dlg; dlg.open=True; self.page.update()
    def show_users(self,e):
        try: users=supabase.admin_list_profiles().data or []
        except Exception as ex: self.page.show_snack_bar(ft.SnackBar(ft.Text(str(ex)))); return
        content=ft.Column([ft.ListTile(title=ft.Text(u.get("full_name","—")),subtitle=ft.Text(f"{u.get('role','—')} • {u.get('class_name') or 'без класса'}")) for u in users],scroll=ft.ScrollMode.AUTO)
        dlg=ft.AlertDialog(title=ft.Text("Пользователи"),content=ft.Container(content=content,width=500,height=500),actions=[ft.TextButton("Закрыть",on_click=lambda e:self._close_dialog(dlg))])
        self.page.dialog=dlg; dlg.open=True; self.page.update()
    def _close_dialog(self,dlg):
        dlg.open=False; self.page.update()
    def logout(self,e):
        try:supabase.sign_out()
        except:pass
        app_state.clear(); self.page.go("/login")
