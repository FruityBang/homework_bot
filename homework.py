import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import (MessageSendingTrouble, NotOkResponse, ResponseError,
                        ResponseMissingKey, SomethingStrangeError)

load_dotenv()


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 10
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправка сообщения в телеграм."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as error:
        raise MessageSendingTrouble(
            f'Ошибка отправки сообщения в телеграм: {error}')
    else:
        logger.info('Отправлено сообщение в Телеграм')


def get_api_answer(current_timestamp):
    """Запрос к эндпоинту. Возвращает словарь."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}

    logger.info('Отправка запроса к API')

    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except Exception as error:
        raise ResponseError(f'Ошибка получения ответа API: {error}')

    logger.info('Ответ API получен')

    if response.status_code != HTTPStatus.OK:
        raise NotOkResponse('Ошибка доступа к API. Статус код не равен 200')

    return response.json()


def check_response(response):
    """Проверка корректности ответа API. Возврат последней работы."""
    logger.info('Проверка корректности ответа API')

    if not isinstance(response, dict):
        raise TypeError('Ответ API - не словарь')

    homework = response.get('homeworks')

    if 'homeworks' not in response or 'current_date' not in response:
        raise ResponseMissingKey('missing keys')

    if not isinstance(response.get('homeworks'), list):
        raise TypeError('Список - не список')

    logger.info('Ответ API корректен')
    return homework


def parse_status(homework):
    """Достает статус домашней работы. Готовит строку для сообщения."""
    logger.info('Проверка статуса')

    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')

    if 'homework_name' not in homework or 'status' not in homework:
        raise KeyError('missing keys in homework')

    if homework_status not in HOMEWORK_STATUSES:
        raise SomethingStrangeError('странные дела')

    verdict = HOMEWORK_STATUSES.get(homework_status)
    logger.info('Статус достат')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка доступности переменных окружеия."""
    logger.debug('проверка токенов')
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        sys.exit('Отсутствуют токены')

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    homework = None
    message = None
    prev_message = None

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework_updated = check_response(response)

            if homework_updated:
                message = parse_status(homework_updated[0])
            else:
                logger.debug('Никаких изменений')

            if message != prev_message:
                send_message(bot, message)
                prev_message = message

            current_timestamp = response.get('current_date')

        except Exception as error:
            logger.error(f'{error}')
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)

        finally:
            logger.debug('По новой')
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
