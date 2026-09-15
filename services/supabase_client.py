"""Единый сервис Supabase"""
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY, SUPABASE_SERVICE_KEY
from services.local_cache import cache
import threading

_refreshing = set()
_refresh_lock = threading.Lock()


class SupabaseService:
    def __init__(self):
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError("SUPABASE_URL и SUPABASE_KEY обязательны.")
        self.client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        self.admin_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY) if SUPABASE_SERVICE_KEY else None

    @staticmethod
    def _data(res):
        return res.data if hasattr(res, "data") else []

    def _cached(self, key, fetch, default=None, ttl=20):
        cached = cache.get(key)
        if cached is not None:
            age = cache.age(key) or 0
            if age > ttl:
                with _refresh_lock:
                    if key not in _refreshing:
                        _refreshing.add(key)
                        threading.Thread(target=self._refresh_cache, args=(key, fetch), daemon=True).start()
            class R:
                pass
            r = R(); r.data = cached
            return r
        try:
            data = self._data(fetch())
            cache.set(key, data)
            class R:
                pass
            r = R(); r.data = data
            return r
        except Exception:
            if default is not None:
                class R:
                    pass
                r = R(); r.data = default
                return r
            raise

    def _refresh_cache(self, key, fetch):
        try:
            cache.set(key, self._data(fetch()))
        except Exception:
            pass
        finally:
            with _refresh_lock:
                _refreshing.discard(key)

    def cache_profile(self, profile):
        if profile and profile.get("id"):
            cache.set(f"profile:{profile['id']}", profile)

    def get_cached_profile(self, user_id):
        return cache.get(f"profile:{user_id}")

    def save_session(self, session, profile):
        if not session or not profile:
            return
        cache.set("last_session", {
            "access_token": getattr(session, "access_token", None),
            "refresh_token": getattr(session, "refresh_token", None),
            "profile": profile,
        })
        self.cache_profile(profile)

    def get_saved_session(self):
        return cache.get("last_session")

    def clear_saved_session(self):
        cache.delete("last_session")

    def warm_user_cache(self, profile):
        """Предзагрузка основных данных после входа, чтобы следующий запуск был мгновенным."""
        import concurrent.futures
        user_id = profile.get("id")
        role = profile.get("role")
        if not user_id:
            return
        jobs = []
        if role == "student":
            class_name = profile.get("class_name")
            if class_name:
                jobs += [
                    lambda: self.get_timetable_week(class_name),
                    lambda: self.get_homeworks(class_name=class_name),
                    lambda: self.get_marks(student_id=user_id),
                    lambda: self.get_submissions(student_id=user_id),
                ]
        elif role == "teacher":
            assignments = self.get_teacher_assignments(user_id).data or []
            classes = sorted({a.get("class_name") for a in assignments if a.get("class_name")})
            for cls in classes:
                jobs += [
                    lambda cls=cls: self.get_timetable_week(cls),
                    lambda cls=cls: self.get_homeworks(class_name=cls, teacher_id=user_id),
                    lambda cls=cls: self.get_profiles_by_class(cls),
                ]
        elif role == "parent":
            children = self.get_children(user_id).data or []
            jobs.append(lambda: self.get_notifications(user_id))
            for child in children:
                cid = child.get("id")
                cls = child.get("class_name")
                jobs += [lambda cid=cid: self.get_marks(student_id=cid),
                         lambda cid=cid: self.get_submissions(student_id=cid)]
                if cls:
                    jobs.append(lambda cls=cls: self.get_homeworks(class_name=cls))
        elif role == "admin":
            jobs += [lambda: self.get_subjects()]
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(10, max(1, len(jobs)))) as pool:
            list(pool.map(lambda fn: self._safe_warm(fn), jobs))

    @staticmethod
    def _safe_warm(fn):
        try:
            fn()
        except Exception:
            pass

    def sign_in(self, email, password):
        return self.client.auth.sign_in_with_password({"email": email.strip(), "password": password})

    def restore_session(self, access_token, refresh_token):
        return self.client.auth.set_session(access_token, refresh_token)

    def sign_out(self):
        return self.client.auth.sign_out()

    def get_profile(self, user_id):
        key = f"profile:{user_id}"
        cached = cache.get(key)
        if cached is not None:
            if (cache.age(key) or 0) > 60:
                threading.Thread(target=self._refresh_profile, args=(user_id, key), daemon=True).start()
            class R: pass
            r = R(); r.data = cached
            return r
        try:
            res = self.client.table("profiles").select("*").eq("id", user_id).single().execute()
            data = self._data(res) or {}
            cache.set(key, data)
            return res
        except Exception:
            class R: pass
            r = R(); r.data = {}
            return r

    def refresh_profile(self, user_id):
        """Всегда получает профиль из Supabase и заменяет локальный кэш."""
        try:
            res = self.client.table("profiles").select("*").eq("id", user_id).single().execute()
            data = self._data(res) or {}
            if data:
                cache.set(f"profile:{user_id}", data)
            return data
        except Exception:
            return cache.get(f"profile:{user_id}") or {}

    def _refresh_profile(self, user_id, key):
        try:
            data = self._data(self.client.table("profiles").select("*").eq("id", user_id).single().execute()) or {}
            cache.set(key, data)
        except Exception:
            pass

    def get_profiles_by_role(self, role):
        return self._cached(f"profiles:role:{role}", lambda: self.client.table("profiles").select("*").eq("role", role).order("full_name").execute(), [])

    def get_profiles_by_class(self, class_name):
        return self._cached(f"profiles:class:{class_name}", lambda: self.client.table("profiles").select("*").eq("class_name", class_name).order("full_name").execute(), [])

    def refresh_profiles_by_class(self, class_name):
        data = self._data(self.client.table("profiles").select("*").eq("class_name", class_name).order("full_name").execute()) or []
        cache.set(f"profiles:class:{class_name}", data)
        return data

    def get_students_for_class(self, class_name):
        """Получает учеников конкретной секции, например 9Б.
        Сначала точное совпадение, затем нормализованное. Сопоставление только
        по номеру класса используется как последний резервный вариант.
        """
        target = self._norm_class(class_name)
        key = f"students:class:{class_name}"
        cached = cache.get(key)
        if cached is not None and (cache.age(key) or 0) <= 30:
            return cached
        try:
            exact = self._data(
                self.client.table("profiles").select("*").eq("class_name", class_name).eq("role", "student").order("full_name").execute()
            ) or []
            if exact:
                cache.set(key, exact)
                return exact

            all_students = self._data(
                self.client.table("profiles").select("*").eq("role", "student").order("full_name").execute()
            ) or []

            def norm(value):
                return self._norm_class(value)

            exact_norm = [row for row in all_students if norm(row.get("class_name")) == target]
            if exact_norm:
                cache.set(key, exact_norm)
                return exact_norm

            import re
            target_grade = re.match(r"(\d{1,2})", str(class_name or ""))
            target_grade = target_grade.group(1) if target_grade else ""
            if target_grade:
                # Если секция не совпала, но в БД есть только один класс этой параллели,
                # считаем его тем же классом. Не смешиваем 9А и 9Б, если обе секции существуют.
                grade_rows = [row for row in all_students if re.match(r"(\d{1,2})", str(row.get("class_name") or "")) and re.match(r"(\d{1,2})", str(row.get("class_name") or "")).group(1) == target_grade]
                sections = {norm(row.get("class_name")) for row in grade_rows}
                if len(sections) == 1:
                    cache.set(key, grade_rows)
                    return grade_rows
            cache.set(key, [])
            return []
        except Exception:
            return cache.get(key) or []

    def get_children(self, parent_id):
        return self._cached(f"user:{parent_id}:children", lambda: self.client.table("profiles").select("*").eq("parent_id", parent_id).order("full_name").execute(), [])

    def update_profile(self, user_id, data):
        res = self.client.table("profiles").update(data).eq("id", user_id).execute()
        current = cache.get(f"profile:{user_id}") or {"id": user_id}
        current.update(data)
        cache.set(f"profile:{user_id}", current)
        return res

    def get_subjects(self):
        return self._cached("subjects", lambda: self.client.table("subjects").select("*").order("name").execute(), [])

    def get_subject(self, subject_id):
        return self._cached(f"subject:{subject_id}", lambda: self.client.table("subjects").select("*").eq("id", subject_id).single().execute(), {})

    def get_teacher_assignments(self, teacher_id):
        return self._cached(f"user:{teacher_id}:assignments", lambda: self.client.table("teacher_assignments").select("*, subjects(name)").eq("teacher_id", teacher_id).order("class_name").execute(), [])

    def refresh_teacher_assignments(self, teacher_id):
        data = self._data(self.client.table("teacher_assignments").select("*, subjects(name)").eq("teacher_id", teacher_id).order("class_name").execute()) or []
        cache.set(f"user:{teacher_id}:assignments", data)
        return data

    def get_teacher_classes(self, teacher_id):
        return self.get_teacher_assignments(teacher_id)

    @staticmethod
    def _norm_class(value):
        v = str(value or "").strip().lower().replace("класс", "").replace("класса", "")
        v = v.replace("-", "")
        return "".join(ch for ch in v if ch.isalnum())

    @staticmethod
    def infer_test_class(email, current=None):
        """Канонический класс для тестовых аккаунтов проекта.
        В продакшене класс берётся из profiles.class_name.
        """
        import re
        local = str(email or "").split("@", 1)[0].lower()
        m = re.fullmatch(r"student(\d+)", local)
        if not m:
            return str(current or "").strip() or None
        number = int(m.group(1))
        mapping = {4: "5А", 9: "9Б", 11: "11Б"}
        return mapping.get(number, str(current or f"{number} класс").strip())

    @classmethod
    def canonical_class_for_profile(cls, profile):
        if not profile:
            return None
        return cls.infer_test_class(profile.get("email"), profile.get("class_name"))

    def _class_aliases(self, class_name):
        raw = str(class_name or "").strip()
        aliases = [raw]
        norm = self._norm_class(raw)
        if norm and norm not in aliases:
            aliases.append(norm)
        if norm.endswith("а") and norm[:-1].isdigit():
            aliases.append(norm[:-1])
        if norm.isdigit():
            aliases.append(f"{norm} класс")
        return list(dict.fromkeys(aliases))

    def get_timetable(self, class_name, day_of_week=None):
        suffix = f":day:{day_of_week}" if day_of_week is not None else ":week"
        return self._cached(f"timetable:{class_name}{suffix}", lambda: self._timetable_query(class_name, day_of_week), [])

    def _timetable_query(self, class_name, day_of_week):
        q = self.client.table("timetable").select("*, subjects(name)").eq("class_name", class_name)
        if day_of_week is not None:
            q = q.eq("day_of_week", day_of_week)
        result = q.order("day_of_week").order("lesson_number").execute()
        data = result.data or []
        if data:
            return result

        # Fallback: старые БД часто содержат "9", "9 класс" или "9А".
        # Один и тот же класс должен находиться независимо от формата записи.
        all_q = self.client.table("timetable").select("*, subjects(name)")
        if day_of_week is not None:
            all_q = all_q.eq("day_of_week", day_of_week)
        all_rows = all_q.order("day_of_week").order("lesson_number").execute().data or []
        target = self._norm_class(class_name)
        matched = [row for row in all_rows if self._norm_class(row.get("class_name")) == target]
        if not matched:
            import re
            m = re.match(r"\s*(\d{1,2})", str(class_name or ""))
            target_grade = m.group(1) if m else ""
            if target_grade:
                matched = []
                for row in all_rows:
                    rm = re.match(r"\s*(\d{1,2})", str(row.get("class_name") or ""))
                    if rm and rm.group(1) == target_grade:
                        matched.append(row)
        class R:
            pass
        r = R(); r.data = matched
        return r

    def get_timetable_week(self, class_name):
        return self._cached(f"timetable:{class_name}:week", lambda: self._timetable_query(class_name, None), [])

    def refresh_timetable_week(self, class_name):
        data = self._data(self._timetable_query(class_name, None)) or []
        cache.set(f"timetable:{class_name}:week", data)
        return data

    def get_homeworks(self, class_name=None, subject_id=None, teacher_id=None):
        parts = [class_name or "*", subject_id or "*", teacher_id or "*"]
        key = "homeworks:" + ":".join(parts)
        def fetch():
            q = self.client.table("homeworks").select("*, subjects(name), profiles(full_name)")
            if class_name: q = q.eq("class_name", class_name)
            if subject_id: q = q.eq("subject_id", subject_id)
            if teacher_id: q = q.eq("teacher_id", teacher_id)
            return q.order("due_date").execute()
        return self._cached(key, fetch, [])

    def get_homework(self, homework_id):
        return self._cached(f"homework:{homework_id}", lambda: self.client.table("homeworks").select("*, subjects(name)").eq("id", homework_id).single().execute(), {})

    def create_homework(self, data):
        res = self.client.table("homeworks").insert(data).execute()
        # Refresh caches belonging to affected class/teacher on next access.
        cache.clear_prefix("homeworks:")
        if getattr(res, "data", None):
            row = res.data[0] if isinstance(res.data, list) else res.data
            if row.get("id"):
                cache.set(f"homework:{row['id']}", row)
        return res

    def update_homework(self, homework_id, data):
        res = self.client.table("homeworks").update(data).eq("id", homework_id).execute()
        cache.delete(f"homework:{homework_id}")
        return res

    def get_submissions(self, homework_id=None, student_id=None, status=None):
        key = "submissions:" + ":".join([homework_id or "*", student_id or "*", status or "*"])
        def fetch():
            q = self.client.table("submissions").select("*, profiles(full_name), homeworks(topic, paragraph, exercise, due_date, task_type, test_questions, teacher_id, class_name)")
            if homework_id: q = q.eq("homework_id", homework_id)
            if student_id: q = q.eq("student_id", student_id)
            if status: q = q.eq("status", status)
            return q.order("submitted_at", desc=True).execute()
        return self._cached(key, fetch, [])

    def submit_homework(self, data):
        res = self.client.table("submissions").insert(data).execute()
        cache.clear_prefix("submissions:")
        return res

    def update_submission(self, submission_id, data):
        return self.client.table("submissions").update(data).eq("id", submission_id).execute()

    def get_marks(self, student_id=None, class_name=None, subject_id=None, category=None):
        key = "marks:" + ":".join([student_id or "*", class_name or "*", subject_id or "*", category or "*"])
        def fetch():
            q = self.client.table("marks").select("""
                id, value, category, comment, created_at, class_name, student_id, subject_id, teacher_id,
                subjects(name),
                student:profiles!marks_student_id_fkey(full_name),
                teacher:profiles!marks_teacher_id_fkey(full_name)
            """)
            if student_id: q = q.eq("student_id", student_id)
            if class_name: q = q.eq("class_name", class_name)
            if subject_id: q = q.eq("subject_id", subject_id)
            if category: q = q.eq("category", category)
            return q.order("created_at", desc=True).execute()
        return self._cached(key, fetch, [])

    def add_mark(self, data):
        res = self.client.table("marks").insert(data).execute()
        cache.clear_prefix("marks:")
        return res

    def get_notifications(self, parent_id):
        return self._cached(f"user:{parent_id}:notifications", lambda: self.client.table("notifications").select("*").eq("parent_id", parent_id).order("created_at", desc=True).execute(), [])

    def add_notification(self, data): return self.client.table("notifications").insert(data).execute()
    def mark_notification_read(self, notification_id): return self.client.table("notifications").update({"is_read": True}).eq("id", notification_id).execute()

    def get_student_total_xp(self, student_id):
        return self._cached(f"user:{student_id}:xp", lambda: self.client.table("xp_log").select("xp_amount").eq("student_id", student_id).execute(), [])
    def add_xp(self, data): return self.client.table("xp_log").insert(data).execute()

    def upload_file(self, bucket, path, file_data, content_type="image/jpeg"):
        return self.client.storage.from_(bucket).upload(path, file_data, {"content-type": content_type, "upsert": "true"})
    def get_public_url(self, bucket, path): return self.client.storage.from_(bucket).get_public_url(path)

    def admin_create_user(self, email, password, user_metadata):
        if not self.admin_client: raise RuntimeError("SUPABASE_SERVICE_KEY не настроен.")
        return self.admin_client.auth.admin.create_user({"email": email.strip(), "password": password, "email_confirm": True, "user_metadata": user_metadata})
    def admin_update_profile(self, user_id, data):
        if not self.admin_client: raise RuntimeError("SUPABASE_SERVICE_KEY не настроен.")
        return self.admin_client.table("profiles").update(data).eq("id", user_id).execute()
    def admin_list_profiles(self):
        if not self.admin_client: raise RuntimeError("SUPABASE_SERVICE_KEY не настроен.")
        return self.admin_client.table("profiles").select("*").order("full_name").execute()
    def admin_count(self, table):
        if not self.admin_client: raise RuntimeError("SUPABASE_SERVICE_KEY не настроен.")
        return self.admin_client.table(table).select("id", count="exact").limit(1).execute()


supabase = SupabaseService()
