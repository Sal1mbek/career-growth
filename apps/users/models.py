# Пользователи и профили
from datetime import date
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.base_user import BaseUserManager
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


class CustomUserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email обязателен")
        email = self.normalize_email(email)
        extra_fields.setdefault("is_active", True)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", CustomUser.UserRole.ROOT)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Суперпользователь должен иметь is_staff=True")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Суперпользователь должен иметь is_superuser=True")

        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractUser):
    """Пользователь с логином по email и ролями."""

    class UserRole(models.TextChoices):
        OFFICER = 'OFFICER', _('Офицер')
        COMMANDER = 'COMMANDER', _('Командир')
        HR = 'HR', _('HR-специалист')
        ADMIN = 'ADMIN', _('Администратор')
        ROOT = 'ROOT', _('ROOT Администратор')

    username = None
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=UserRole.choices)
    email_verified = models.BooleanField(default=False)
    is_blocked = models.BooleanField(default=False)

    # 2FA
    twofa_enabled = models.BooleanField(default=False)
    twofa_secret = models.CharField(max_length=64, blank=True)

    # Security
    failed_login_attempts = models.PositiveSmallIntegerField(default=0, db_index=True)
    last_failed_login = models.DateTimeField(null=True, blank=True)
    password_changed_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = CustomUserManager()


# --------- БАЗОВЫЙ Профиль (общие поля для офицера и командира) ---------
class BasePersonProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    # опционально — если хотим переписать ФИО; иначе берём из user.{first,last}_name
    full_name = models.CharField(max_length=255, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True)

    photo = models.ImageField(upload_to='profiles/photos/', null=True, blank=True)
    iin = models.CharField(
        max_length=12, blank=True, null=True, unique=True,
        validators=[RegexValidator(r'^\d{12}$', message="ИИН должен содержать 12 цифр")]
    )
    birth_place = models.CharField(max_length=255, blank=True)
    nationality = models.CharField(max_length=64, blank=True)

    class MaritalStatus(models.TextChoices):
        SINGLE = 'SINGLE', _('холост/не замужем')
        MARRIED = 'MARRIED', _('женат/замужем')
        DIVORCED = 'DIVORCED', _('разведён/разведена')
        WIDOWED = 'WIDOWED', _('вдова/вдовец')

    marital_status = models.CharField(max_length=16, choices=MaritalStatus.choices, blank=True)
    combat_participation = models.BooleanField(default=False)
    combat_notes = models.CharField(max_length=255, blank=True)

    rank = models.ForeignKey('directory.Rank', on_delete=models.CASCADE, null=True)
    unit = models.ForeignKey('directory.Unit', on_delete=models.CASCADE, null=True)
    current_position = models.ForeignKey('directory.Position', on_delete=models.SET_NULL, null=True, blank=True)

    service_start_date = models.DateField(null=True, blank=True)

    class Meta:
        abstract = True

    def _short(self):
        name = self.full_name or getattr(self.user, "email", "")
        rank = self.rank.name if self.rank else ""
        unit = self.unit.name if self.unit else ""
        parts = [p for p in [name, rank, unit] if p]
        return " / ".join(parts)


class OfficerProfile(BasePersonProfile):
    # 1) Звание: текст про присвоение (пока просто "приказ/дата" или rank.since как строка)
    rank_assignment_info = models.CharField(max_length=255, blank=True)  # например: "Приказ №123 от 2023-08-01"

    # 2) Личное
    personal_number = models.CharField(max_length=32, blank=True)  # "З-516544"
    children_count = models.PositiveSmallIntegerField(default=0)

    # 2б) Гос. награды / взыскания (как свободный текст)
    awards = models.TextField(blank=True)  # "Благодарственное письмо МО (2022)"
    penalties = models.TextField(blank=True)  # "Строгий выговор (2019)"

    # 3) Образование (короткие строки)
    education_civil = models.CharField(max_length=255, blank=True)  # "АУЭС (2012)"
    education_military = models.CharField(max_length=255, blank=True)  # "НУО (АСУ, 2018)"

    # 5) История должностей — лёгкий JSON без связей
    # Формат элемента: {"from": "YYYY-MM-DD", "to": "YYYY-MM-DD|null", "position": "строка"}
    service_history = models.JSONField(default=list, blank=True)

    def __str__(self):
        return self._short()


class OfficerLanguage(models.Model):
    """Знание языков (мультирядовость)."""
    class Level(models.TextChoices):
        BASIC = 'BASIC', _('со словарём')
        INTERMEDIATE = 'INTERMEDIATE', _('средний')
        ADVANCED = 'ADVANCED', _('свободно')

    officer = models.ForeignKey(OfficerProfile, on_delete=models.CASCADE,
                                related_name='languages')
    language = models.CharField(max_length=64)     # 'русский', 'английский', 'казахский'
    level = models.CharField(max_length=16, choices=Level.choices, default=Level.BASIC)

    class Meta:
        unique_together = ('officer', 'language')
        ordering = ['language']

    def __str__(self):
        return f"{self.officer_id} - {self.language} ({self.level})"


class CommanderProfile(BasePersonProfile):
    class CommandScope(models.TextChoices):
        PLATOON = 'PLATOON', _('взвод')
        COMPANY = 'COMPANY', _('рота')
        BATTALION = 'BATTALION', _('батальон')
        REGIMENT = 'REGIMENT', _('полк')
        BRIGADE = 'BRIGADE', _('бригада')
        DIVISION = 'DIVISION', _('дивизия')
        OTHER = 'OTHER', _('другое')

    # Уникальные поля командира
    command_title = models.CharField(max_length=128, blank=True, help_text=_("Должность по командованию"))
    command_scope = models.CharField(max_length=16, choices=CommandScope.choices, blank=True)
    appointed_at = models.DateField(null=True, blank=True, help_text=_("Дата назначения командиром"))
    relieved_at = models.DateField(null=True, blank=True, help_text=_("Дата освобождения от должности"))
    staff_position = models.BooleanField(default=False, help_text=_("Штабная должность"))
    subordinates_expected = models.PositiveIntegerField(default=0, help_text=_("Плановая численность подчинённых"))

    def __str__(self):
        return self._short()


class CommanderLanguage(models.Model):
    """Знание языков (мультирядовость) для командира."""
    class Level(models.TextChoices):
        BASIC = 'BASIC', _('со словарём')
        INTERMEDIATE = 'INTERMEDIATE', _('средний')
        ADVANCED = 'ADVANCED', _('свободно')

    commander = models.ForeignKey(CommanderProfile, on_delete=models.CASCADE, related_name='languages')
    language = models.CharField(max_length=64)
    level = models.CharField(max_length=16, choices=Level.choices, default=Level.BASIC)

    class Meta:
        unique_together = ('commander', 'language')
        ordering = ['language']

    def __str__(self):
        return f"{self.commander_id} - {self.language} ({self.level})"


class HRProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='hr_profile')
    responsible_units = models.ManyToManyField('directory.Unit', related_name='hr_responsibles', blank=True)

    def __str__(self):
        return self.user.email


class CommanderAssignment(models.Model):
    commander = models.ForeignKey(CommanderProfile, on_delete=models.CASCADE)
    officer = models.ForeignKey(OfficerProfile, on_delete=models.CASCADE)
    since = models.DateField(default=date.today)
    until = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = ('commander', 'officer', 'since')
        indexes = [
            models.Index(fields=["commander", "officer"]),
            models.Index(fields=["since", "until"]),
        ]
