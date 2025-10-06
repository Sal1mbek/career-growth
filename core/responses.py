from rest_framework.response import Response
from rest_framework import status


class APIResponse(Response):
    """Стандартизированные ответы API"""

    @staticmethod
    def success(data=None, message="OK", code=status.HTTP_200_OK):
        return Response({"success": True, "message": message, "data": data}, status=code)

    @staticmethod
    def created(data=None, message="Создано"):
        return Response({"success": True, "message": message, "data": data}, status=status.HTTP_201_CREATED)

    @staticmethod
    def not_found(message="Не найдено"):
        return Response({"success": False, "message": message}, status=status.HTTP_404_NOT_FOUND)

    @staticmethod
    def validation_error(errors, message="Ошибка валидации"):
        return Response({"success": False, "message": message, "errors": errors}, status=status.HTTP_400_BAD_REQUEST)

    @staticmethod
    def unauthorized(message="Не авторизован"):
        return Response({"success": False, "message": message}, status=status.HTTP_401_UNAUTHORIZED)

    @staticmethod
    def forbidden(message="Доступ запрещён"):
        return Response({"success": False, "message": message}, status=status.HTTP_403_FORBIDDEN)

    @staticmethod
    def error(message="Внутренняя ошибка сервера", code=status.HTTP_500_INTERNAL_SERVER_ERROR):
        return Response({"success": False, "message": message}, status=code)
