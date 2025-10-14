# Поощрения Взыскания
from django.db import models
from django.conf import settings


class MeasureStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Черновик'
    SUBMITTED = 'SUBMITTED', 'На утверждении'
    APPROVED = 'APPROVED', 'Утверждено'
    REJECTED = 'REJECTED', 'Отклонено'
    EXECUTED = 'EXECUTED', 'Исполнено (приказ)'
    REVOKED = 'REVOKED', 'Отменено'


class TargetType(models.TextChoices):
    OFFICER = 'OFFICER', 'Офицер'
    UNIT = 'UNIT', 'Подразделение'


class BaseMeasure(models.Model):
    """Общие поля для поощрений и взысканий."""
    target_type = models.CharField(max_length=16, choices=TargetType.choices, default=TargetType.OFFICER)
    officer = models.ForeignKey('users.OfficerProfile', null=True, blank=True, on_delete=models.CASCADE,
                                related_name="%(class)ss")
    unit = models.ForeignKey('directory.Unit', null=True, blank=True, on_delete=models.CASCADE)

    is_collective = models.BooleanField(default=False)

    title = models.CharField(max_length=255, blank=True)  # например "Объявлена благодарность"
    description = models.TextField(blank=True)

    initiator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                  related_name="%(class)s_initiated")
    status = models.CharField(max_length=16, choices=MeasureStatus.choices, default=MeasureStatus.DRAFT, db_index=True)

    # утверждение (MVP — одноступенчатое)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="%(class)s_approved")
    approved_at = models.DateTimeField(null=True, blank=True)
    approval_comment = models.TextField(blank=True)

    # реквизиты приказа (исполнение)
    order_number = models.CharField(max_length=64, blank=True)
    order_date = models.DateField(null=True, blank=True)

    # период действия (актуально для взысканий; для поощрений можно игнорировать)
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ['-created_at']

    def __str__(self):
        target = self.officer.full_name if self.officer else (self.unit.name if self.unit else "—")
        # title может быть пустым — используем имя класса
        return f"{self.title or self.__class__.__name__} → {target}"


class RewardType(models.TextChoices):
    THANKS = 'THANKS', 'Благодарность'
    LIFT_SANCTION = 'LIFT_SANCTION', 'Досрочное снятие взыскания'
    CERTIFICATE = 'CERTIFICATE', 'Грамота'
    GIFT = 'GIFT', 'Ценный подарок'
    EARLY_RANK = 'EARLY_RANK', 'Досрочное присвоение звания'
    HONOR_BOARD = 'HONOR_BOARD', 'Доска почёта / Книга отличников'
    STATE_AWARD = 'STATE_AWARD', 'Гос./ведомственная награда'
    EXTRA_VACATION = 'EXTRA_VACATION', 'Отпуск вне очереди / доп. отдых'
    DISCHARGE_THANKS = 'DISCHARGE_THANKS', 'Поощрительное увольнение в запас'


class Reward(BaseMeasure):
    reward_type = models.CharField(max_length=32, choices=RewardType.choices)
    linked_sanction = models.ForeignKey('discipline.Sanction', null=True, blank=True, on_delete=models.SET_NULL,
                                        help_text="Для досрочного снятия взыскания")

    class Meta(BaseMeasure.Meta):
        indexes = [
            models.Index(fields=["officer", "status"]),
            models.Index(fields=["reward_type", "status"]),
        ]

    def __str__(self):
        t = self.officer.full_name if self.officer else (self.unit.name if self.unit else "—")
        return f"{self.get_reward_type_display()} → {t}"


class SanctionType(models.TextChoices):
    REMARK = 'REMARK', 'Замечание'
    REPRIMAND = 'REPRIMAND', 'Выговор'
    SEVERE_REPRIMAND = 'SEVERE_REPRIMAND', 'Строгий выговор'
    WARNING_INCOMPETENCE = 'WARNING_INCOMPETENCE', 'Предупреждение о неполном служебном соответствии'
    DENY_LEAVE = 'DENY_LEAVE', 'Лишение очередного увольнения'
    DEMOTION_POSITION = 'DEMOTION_POSITION', 'Снижение в должности'
    DEMOTION_RANK = 'DEMOTION_RANK', 'Снижение в звании'
    DISCIPLINARY_ARREST = 'DISCIPLINARY_ARREST', 'Дисциплинарный арест'
    DISMISSAL = 'DISMISSAL', 'Увольнение по отрицательным мотивам'


class Sanction(BaseMeasure):
    sanction_type = models.CharField(max_length=32, choices=SanctionType.choices)
    lifted_at = models.DateField(null=True, blank=True)  # дата досрочного снятия (если Reward.LIFT_SANCTION)

    class Meta(BaseMeasure.Meta):
        indexes = [
            models.Index(fields=["officer", "status"]),
            models.Index(fields=["sanction_type", "status"]),
        ]

    def __str__(self):
        t = self.officer.full_name if self.officer else (self.unit.name if self.unit else "—")
        return f"{self.get_sanction_type_display()} → {t}"
