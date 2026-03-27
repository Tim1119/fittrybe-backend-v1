"""
Chat app signals — auto-create chatrooms on profile publish,
sync client membership changes to chatroom membership.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver


def _update_member_count(chatroom):
    from apps.chat.models import Chatroom, ChatroomMember

    count = ChatroomMember.objects.filter(chatroom=chatroom, is_active=True).count()
    Chatroom.objects.filter(pk=chatroom.pk).update(member_count=count)


@receiver(post_save, sender="profiles.TrainerProfile")
def create_trainer_chatroom(sender, instance, **kwargs):
    from apps.chat.models import Chatroom, ChatroomMember

    if not instance.is_published:
        return

    name = f"{instance.full_name}'s Community"
    chatroom, created = Chatroom.objects.get_or_create(
        trainer=instance,
        defaults={"name": name},
    )
    if created:
        ChatroomMember.objects.get_or_create(
            chatroom=chatroom,
            user=instance.user,
            defaults={"role": ChatroomMember.Role.ADMIN},
        )
        _update_member_count(chatroom)


@receiver(post_save, sender="profiles.GymProfile")
def create_gym_chatroom(sender, instance, **kwargs):
    from apps.chat.models import Chatroom, ChatroomMember

    if not instance.is_published:
        return

    name = f"{instance.gym_name}'s Community"
    chatroom, created = Chatroom.objects.get_or_create(
        gym=instance,
        defaults={"name": name},
    )
    if created:
        ChatroomMember.objects.get_or_create(
            chatroom=chatroom,
            user=instance.user,
            defaults={"role": ChatroomMember.Role.ADMIN},
        )
        _update_member_count(chatroom)


@receiver(post_save, sender="clients.ClientMembership")
def sync_client_to_chatroom(sender, instance, created, **kwargs):
    from apps.chat.models import Chatroom, ChatroomMember

    chatroom = None
    if instance.trainer_id:
        chatroom = Chatroom.objects.filter(
            trainer_id=instance.trainer_id, is_active=True
        ).first()
    elif instance.gym_id:
        chatroom = Chatroom.objects.filter(
            gym_id=instance.gym_id, is_active=True
        ).first()

    if not chatroom:
        return

    if instance.deleted_at:
        # Soft-deleted membership → deactivate chatroom member
        ChatroomMember.objects.filter(
            chatroom=chatroom,
            user=instance.client.user,
        ).update(is_active=False)
    else:
        member, mc = ChatroomMember.objects.get_or_create(
            chatroom=chatroom,
            user=instance.client.user,
            defaults={
                "role": ChatroomMember.Role.MEMBER,
                "is_active": True,
            },
        )
        if not mc and not member.is_active:
            member.is_active = True
            member.save(update_fields=["is_active"])

    _update_member_count(chatroom)
