import sys
import random
import time
import logging

import requests
from vk_api import VkApi


from constants import (PRACTICUM_TOKEN, VK_TOKEN, VK_USER_ID, RETRY_PERIOD,
                       ENDPOINT, HEADERS, HOMEWORK_VERDICTS)


logging.basicConfig(
    level=logging.DEBUG,
    stream=sys.stdout,
    format='%(asctime)s [%(levelname)s] %(message)s'
)


def check_tokens():
    '''Проверяет наличие необходимых токенов.'''
    missing = []
    if not PRACTICUM_TOKEN:
        missing.append('PRACTICUM_TOKEN')
    if not VK_TOKEN:
        missing.append('VK_TOKEN')
    if not VK_USER_ID:
        missing.append('VK_USER_ID')
    if missing:
        for var in missing:
            logging.critical(
                f'Отсутствует обязательная переменная окружения: {var}'
            )
        logging.critical('Программа принудительно остановлена.')
        raise SystemExit('Отсутствуют обязательные переменные окружения')
    return True


def get_api_answer(timestamp):
    '''Запрашивает статусы домашних работ у API Практикума.'''
    try:
        response = requests.get(ENDPOINT, headers=HEADERS,
                                params={'from_date': timestamp})
    except requests.RequestException as error:
        logging.error(f'Эндпоинт {ENDPOINT} недоступен: {error}')
        raise ConnectionError(f'Эндпоинт недоступен: {error}')

    if response.status_code != 200:
        logging.error(f'Эндпоинт {ENDPOINT} вернул код {response.status_code}')
        raise ConnectionError(f'Код ответа API: {response.status_code}')
    try:
        return response.json()
    except Exception as error:
        logging.error(f'Произошла ошибка: {error}')
        raise


def check_response(response):
    '''Проверяет ответ API на валидность.'''
    if not isinstance(response, dict):
        raise TypeError('Ответ API не является словарём')
    if 'homeworks' not in response or 'current_date' not in response:
        raise KeyError('Отсутствуют ожидаемые ключи в ответе API')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError('homeworks не является списком')
    required_keys = {'status', 'homework_name'}
    for homework in homeworks:
        if not required_keys.issubset(homework.keys()):
            raise KeyError(
                'Отсутствуют ожидаемые ключи в информации о домашней работе'
            )
        if homework['status'] not in HOMEWORK_VERDICTS:
            raise ValueError(
                f'Неожиданный статус домашней работы: {homework["status"]}'
            )
    return True


def parse_status(homework):
    '''Формирует строку для пользователя.'''
    status = homework.get('status')
    homework_name = homework.get('homework_name')

    if homework_name is None:
        logging.error('Отсутствует ключ homework_name')
        raise KeyError('Отсутствует ключ homework_name')

    if status not in HOMEWORK_VERDICTS:
        logging.error(f'Неожиданный статус домашней работы: {status}')
        raise ValueError(f'Неизвестный статус: {status}')

    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def send_message(vk, message):
    '''Отправляет сообщение пользователю.'''
    try:
        vk.messages.send(
            user_id=VK_USER_ID,
            message=message,
            random_id=random.randint(1, 100000)
        )
        logging.debug(f'Бот отправил сообщение: "{message}"')
    except Exception as error:
        logging.error(f'Сбой при отправке сообщения в VK: {error}')


def main():
    '''Основная логика работы бота.'''
    check_tokens()
    vk_session = VkApi(token=VK_TOKEN)
    vk = vk_session.get_api()
    timestamp = int(time.time())
    sent_errors = set()
    send_message(vk, 'Бот запущен!')
    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            timestamp = response.get('current_date')
            homeworks = response.get('homeworks', [])

            if homeworks:
                for homework in homeworks:
                    message = parse_status(homework)
                    send_message(vk, message)
            else:
                logging.debug('Новых статусов нет')

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            if message not in sent_errors:
                try:
                    send_message(vk, message)
                    sent_errors.add(message)
                except Exception:
                    logging.error(
                        'Не удалось отправить сообщение об ошибке в VK'
                    )

        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
