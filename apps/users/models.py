# Пользователи и профили
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


class OfficerProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='officer_profile')

    # опционально — если хотим переписать ФИО; иначе берём из user.{first,last}_name
    full_name = models.CharField(max_length=255, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True)

    photo = models.ImageField(upload_to='officers/photos/', null=True, blank=True)
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

    rank = models.ForeignKey('directory.Rank', on_delete=models.PROTECT, null=True)
    unit = models.ForeignKey('directory.Unit', on_delete=models.PROTECT, null=True)
    current_position = models.ForeignKey('directory.Position', on_delete=models.SET_NULL, null=True, blank=True)

    service_start_date = models.DateField()

    def __str__(self):
        name = self.full_name or self.user.email
        rank = self.rank.name if self.rank else ""
        unit = self.unit.name if self.unit else ""
        parts = [p for p in [name, rank, unit] if p]
        return " / ".join(parts)


class EducationEntry(models.Model):
    """Пункты образования (гражданское / военно-специальное)."""
    class EducationType(models.TextChoices):
        CIVIL = 'CIVIL', _('Гражданское')
        MIL = 'MIL', _('Военно-специальное')

    officer = models.ForeignKey(OfficerProfile, on_delete=models.CASCADE, related_name='educations')
    type = models.CharField(max_length=8, choices=EducationType.choices)
    year = models.PositiveIntegerField(validators=[MinValueValidator(1900)])
    institution = models.CharField(max_length=255)     # школа/вуз/центр
    specialty = models.CharField(max_length=255, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ['type', 'year']


class ServiceRecord(models.Model):
    """История службы (таймлайн)."""
    officer = models.ForeignKey(OfficerProfile, on_delete=models.CASCADE, related_name='service_records')
    year = models.PositiveIntegerField(validators=[MinValueValidator(1900)], null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    title = models.CharField(max_length=255)           # должность/роль
    unit_name = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['start_date', 'year', 'id']


class OfficerLanguage(models.Model):
    """Знание языков."""
    class Level(models.TextChoices):
        BASIC = 'BASIC', _('со словарём')
        INTERMEDIATE = 'INTERMEDIATE', _('средний')
        ADVANCED = 'ADVANCED', _('свободно')

    officer = models.ForeignKey(OfficerProfile, on_delete=models.CASCADE, related_name='languages')
    language = models.CharField(max_length=64)         # 'русский', 'английский', 'казахский'
    level = models.CharField(max_length=16, choices=Level.choices, default=Level.BASIC)

    class Meta:
        unique_together = ('officer', 'language')
        ordering = ['language']



class CommanderProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='commander_profile')
    unit = models.ForeignKey('directory.Unit', on_delete=models.PROTECT)

    def __str__(self):
        return f"{self.user.email} / {self.unit.name if self.unit else ''}"


class HRProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='hr_profile')
    responsible_units = models.ManyToManyField('directory.Unit', related_name='hr_responsibles', blank=True)

    def __str__(self):
        return self.user.email


class CommanderAssignment(models.Model):
    commander = models.ForeignKey(CommanderProfile, on_delete=models.CASCADE)
    officer = models.ForeignKey(OfficerProfile, on_delete=models.CASCADE)
    since = models.DateField()
    until = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = ('commander', 'officer', 'since')
