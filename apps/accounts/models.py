from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Extended User model with role-based access for procurement screening."""

    class Role(models.TextChoices):
        ADMINISTRATOR = 'ADMIN', 'Administrator'
        AUDITOR = 'AUDITOR', 'Auditor/Reviewer'

    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.AUDITOR,
    )

    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return f'{self.username} ({self.get_role_display()})'

    @property
    def is_administrator(self):
        return self.role == self.Role.ADMINISTRATOR

    @property
    def is_auditor(self):
        return self.role == self.Role.AUDITOR
