"""Рейтинг класса по XP."""
import flet as ft
from models.user import app_state
from services.supabase_client import supabase
from components.topbar import TopBar

class LeaderboardScreen(ft.View):
    def __init__(self,page,on_navigate):
        super().__init__(route="/leaderboard"); self.page=page; self.on_navigate=on_navigate; self.user=app_state.current_user; self.build_ui()
    def build_ui(self):
        col=ft.Column(spacing=6); me_xp=0; me_place=0
        try:
            students=supabase.get_profiles_by_class(self.user.class_name).data or []
            rows=[]
            for s in students:
                if s.get("role")!="student": continue
                xp=supabase.get_student_total_xp(s["id"]).data or []
                total=sum(int(x.get("xp_amount",0) or 0) for x in xp)
                subs=supabase.get_submissions(student_id=s["id"]).data or []
                rows.append({"id":s["id"],"name":s.get("full_name","Ученик"),"xp":total,
                             "hw_done":sum(1 for x in subs if x.get("status")=="checked"),"tests":len(subs)})
            rows.sort(key=lambda x:x["xp"],reverse=True)
            for i,s in enumerate(rows,1):
                if s["id"]==self.user.user_id: me_xp=s["xp"]; me_place=i
                icon="🥇" if i==1 else "🥈" if i==2 else "🥉" if i==3 else str(i)
                col.controls.append(ft.Card(content=ft.Container(content=ft.Row([
                    ft.Text(icon,width=35,size=18),ft.CircleAvatar(content=ft.Text(s["name"][0].upper())),
                    ft.Column([ft.Text(s["name"],weight=ft.FontWeight.BOLD),ft.Text(f"ДЗ: {s['hw_done']} • Активности: {s['tests']}",size=11)],expand=True),
                    ft.Text(f"{s['xp']} XP",weight=ft.FontWeight.BOLD)
                ]),padding=10)))
            if not rows: col.controls.append(ft.Text("В классе пока нет участников рейтинга."))
        except Exception as ex: col.controls.append(ft.Text(f"Ошибка: {ex}",color=ft.colors.RED))
        stats=ft.Card(content=ft.Container(content=ft.Row([
            ft.Text(f"Место: {me_place or '—'}",weight=ft.FontWeight.BOLD),
            ft.Text(f"XP: {me_xp}",weight=ft.FontWeight.BOLD)
        ],alignment=ft.MainAxisAlignment.SPACE_EVENLY),padding=14))
        self.controls=[TopBar("🏆 Рейтинг класса"),
            ft.Container(content=ft.Column([stats,ft.Text("Топ учеников",size=18,weight=ft.FontWeight.BOLD),col],scroll=ft.ScrollMode.AUTO,spacing=12),padding=15,expand=True)]
