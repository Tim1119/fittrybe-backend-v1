"""
Token generator for gym trainer invite-accept flow.
"""

from django.contrib.auth.tokens import PasswordResetTokenGenerator


class GymTrainerInviteTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        return str(user.pk) + str(timestamp) + str(user.is_active) + str(user.password)


gym_trainer_invite_token = GymTrainerInviteTokenGenerator()
