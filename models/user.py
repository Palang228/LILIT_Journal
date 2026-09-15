
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class UserSession:
    user_id: str
    email: str
    full_name: str
    role: str
    class_name: Optional[str] = None
    subject_id: Optional[str] = None
    parent_id: Optional[str] = None
    avatar_url: Optional[str] = None
    phone: Optional[str] = None
    metadata: dict = field(default_factory=dict)


class AppState:
    def __init__(self):
        self.current_user: Optional[UserSession] = None
        self.saved_accounts: List[dict] = []
        self.page = None
        self.selected_homework_id: Optional[str] = None
        self.selected_submission_id: Optional[str] = None
        self.selected_teacher_class: Optional[str] = None
        self.selected_grade_student_id: Optional[str] = None

    def set_user(self, user: UserSession):
        self.current_user = user

    def clear(self):
        self.current_user = None
        self.selected_homework_id = None
        self.selected_submission_id = None
        self.selected_teacher_class = None
        self.selected_grade_student_id = None


app_state = AppState()
