from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse


def send_verification_email(user, request):
    """
    Генерирует токен и отправляет ссылку вида:
    /api/v1/auth/verify-email/<uidb64>/<token>/
    """
    token = default_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))

    relative = reverse('verify-email', kwargs={'uidb64': uid, 'token': token})
    link = f"{request.scheme}://{request.get_host()}{relative}"

    html_message = render_to_string('verify_email/email.html', {'link': link, 'user': user})
    subject = 'Career Growth — подтвердите e-mail'
    from_email = None  # будет взят DEFAULT_FROM_EMAIL

    send_mail(
        subject=subject,
        message='',
        from_email=from_email,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=False,
    )
