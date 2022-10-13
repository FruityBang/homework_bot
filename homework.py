import exceptions
import logging
import os
import requests
import sys
import telegram
import time
from dotenv import load_dotenv


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

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправка сообщения в телеграм."""
    logger.info('Отправлено сообщение в Телеграм')
    bot.send_message(TELEGRAM_CHAT_ID, message)


def get_api_answer(current_timestamp):
    """Запрос к эндпоинту. Возвращает словарь."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}

    response = requests.get(ENDPOINT, headers=HEADERS, params=params)

    if response.status_code != 200:
        logger.error('Ошибка доступа к API. Код 300 или там 400!')
        raise exceptions.NotOkResponse('Ошибка доступа к API')
    else:
        response = response.json()
        return response


def check_response(response):
    """Проверка корректности ответа API. Возврат последней работы."""
    if type(response) != dict:
        logger.error('Ответ API - не словарь!')
        raise TypeError('Ответ API - не словарь')
    elif type(response.get('homeworks')) != list:
        logger.error('Список домашек - не список!')
        raise TypeError('Список - не список')
    elif 'homeworks' not in response:
        logger.error('В ответе API отсутствуют требуемые ключи')
        raise exceptions.ResponseMissingKey('missing keys')
    elif len(response.get('homeworks')) == 0:
        homework = response.get('homeworks')
        return homework
    else:
        homework = response.get('homeworks')[0]
        return homework


def parse_status(homework):
    """Достает статус домашне работы. Готовит строку для сообщения."""
    if type(homework) == list:
        return 'Ничего не изменилось'
    elif 'homework_name' not in homework:
        logger.error('Неизвестный ключ ответа')
        raise KeyError('Неизвестный ключ ответа')
    else:
        homework_name = homework.get('homework_name')
        homework_status = homework.get('status')

    verdict = HOMEWORK_STATUSES.get(homework_status)

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка доступности переменных окружеия."""
    logger.debug('проверка токенов')
    if not (PRACTICUM_TOKEN and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID):
        logger.critical('Missing some токэнзз!!11!')
        return False
        sys.exit(2)
    return True


def main():
    """Основная логика работы бота."""
    check_tokens()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())

    homework = None
    message_count = 0

    while check_tokens():
        try:
            response = get_api_answer(current_timestamp)
            homework_updated = check_response(response)

            if type(homework_updated) == list:
                logger.debug('Никаких изменений')
            elif homework_updated != homework:
                homework = homework_updated
                message = parse_status(homework)
                send_message(bot, message)
            else:
                logger.debug('Никаких изменений')

            current_timestamp = response.get('current_date')
            logger.debug('ждем')
            time.sleep(RETRY_TIME)

        except Exception as error:
            if message_count < 1:
                message = f'Сбой в работе программы: {error}'
                send_message(bot, message)
                message_count += 1

            time.sleep(RETRY_TIME)
        else:
            logger.debug('По новой')
            message_count = 0


if __name__ == '__main__':
    main()
