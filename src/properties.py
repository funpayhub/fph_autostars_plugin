from __future__ import annotations

from pytoniq_core.crypto.keys import mnemonic_is_valid

from funpayhub.lib.exceptions import ValidationError
from funpayhub.lib.properties import Properties, StringParameter, ToggleParameter
from funpayhub.lib.base_app.properties_flags import TelegramUIEmojiFlag

from funpayhub.app.properties.flags import ParameterFlags


async def mnemonic_validator(val: str) -> None:
    if not val:
        return

    if not mnemonic_is_valid(val.split(' ')):
        raise ValidationError('Невалидная сид фраза.')


class AutostarsProperties(Properties):
    def __init__(self) -> None:
        super().__init__(
            id='com_github_qvvonk_funpayhub_autostars_plugin',
            name='Autostars',
            description='Настройкаи плагина Autostars.',
            flags=[TelegramUIEmojiFlag('🌟')],
            file='config/com.github.qvvonk.funpayhub.autostars_plugin.toml',
        )

        self.wallet = self.attach_node(WalletProperties())
        self.messages = self.attach_node(MessagesProperties())
        self.other = self.attach_node(Other())


class WalletProperties(Properties):
    def __init__(self):
        super().__init__(
            id='wallet',
            name='Настройки кошелька',
            description='Настройки TON кошелька и Fragment аккаунта.',
            flags=[TelegramUIEmojiFlag('👛')],
        )

        self.cookies = self.attach_node(
            StringParameter(
                id='cookies',
                name='Fragment cookies',
                description='Cookie Fragment аккаунта.',
                default_value='',
                flags=[TelegramUIEmojiFlag('🍪'), ParameterFlags.PROTECT_VALUE],
            ),
        )

        self.fragment_hash = self.attach_node(
            StringParameter(
                id='fragment_hash',
                name='Fragment hash',
                description='API hash Fragment аккаунта.',
                default_value='',
                flags=[TelegramUIEmojiFlag('#️⃣'), ParameterFlags.PROTECT_VALUE],
            ),
        )

        self.mnemonics = self.attach_node(
            StringParameter(
                id='mnemonics',
                name='Сид фраза',
                description='Сид фраза TON кошелька.',
                default_value='',
                flags=[TelegramUIEmojiFlag('🔐'), ParameterFlags.PROTECT_VALUE],
                validator=mnemonic_validator,
            ),
        )


class MessagesProperties(Properties):
    def __init__(self):
        super().__init__(
            id='messages',
            name='Настройки сообщений',
            description='Настройки FunPay сообщений, комментариев к транзакциям и т.д.',
            flags=[TelegramUIEmojiFlag('💬'), ParameterFlags.HIDE_VALUE],
        )

        self.show_ad = self.attach_node(
            ToggleParameter(
                id='show_ad',
                name='Показывать рекламу',
                description='Показывать рекламу в комментарии к TON транзакции',
                default_value=True,
                flags=[TelegramUIEmojiFlag('👻')],
            ),
        )

        self.transaction_completed_message = self.attach_node(
            StringParameter(
                id='transaction_completed_message',
                name='Сообщение о завершении транзакции',
                description='Сообщение, которое будет отправлено в чат покупателю, когда транзакция будет завершена.',
                default_value=(
                    '🌟 $order<counterparty.username>, '
                    '$autostars_amount звёзд успешно переведены на аккаунт $autostars_username.\n\n'
                    '#️⃣ Хэш TON транзакции: $autostars_hash.'
                ),
                flags=[TelegramUIEmojiFlag('✅'), ParameterFlags.HIDE_VALUE],
            ),
        )

        self.transaction_failed_message = self.attach_node(
            StringParameter(
                id='transaction_failed_message',
                name='Сообщение о неудачной транзакции',
                description='Сообщение, которое будет отправлено в чат покупателю, если транзакция завершилась ошибкой.',
                default_value=(
                    '❌ $order<counterparty.username>, не удалось перевести звезды.\n'
                    'Продавец уведомлен и придет на помощь как только сможет!'
                ),
                flags=[TelegramUIEmojiFlag('❌'), ParameterFlags.HIDE_VALUE],
            ),
        )

        self.invalid_username_message = self.attach_node(
            StringParameter(
                id='invalid_username_message',
                name='Невалидный юзернейм',
                description='Сообщение, которое будет отправлено в чат покупателю, если указанный юзернейм невалиден.',
                default_value=(
                    '❌ $order<counterparty.username>, telegram юзернейм по заказу $order<id> невалиден.\n\n'
                    'Проверьте правильность введенного юзернейма и введите команду:\n'
                    '/stars $order<id> ваш_телеграм_юзернейм'
                ),
                flags=[TelegramUIEmojiFlag('🤡'), ParameterFlags.HIDE_VALUE],
            ),
        )

        self.username_not_found_message = self.attach_node(
            StringParameter(
                id='username_not_found_message',
                name='Пользователь не найден',
                description='Сообщение, которое будет отправлено в чат покупателю, если Telegram пользователь не найден.',
                default_value=(
                    '❌ $order<counterparty.username>, не удалось найти Telegram аккаунт с юзернеймом @$autostars_username.\n\n'
                    'Проверьте правильность введенного юзернейма и введите команду:\n'
                    '/stars $order<id> ваш_телеграм_юзернейм'
                ),
                flags=[TelegramUIEmojiFlag('🤡'), ParameterFlags.HIDE_VALUE],
            ),
        )

        self.not_user_username_message = self.attach_node(
            StringParameter(
                id='not_user_username_message',
                name='Не пользовательский юзернейм',
                description='Сообщение, которое будет отправлено в чат покупателю, если указанный юзернейм принадлежит НЕ пользователю (каналу / чату).',
                default_value=(
                    '❌ $order<counterparty.username>, telegram тег @$autostars_username принадлежит не пользователю.\n'
                    'Перевод звезд каналам или чатам не поддерживается.\n\n'
                    'Пожалуйста, укажите юзернейм, который принадлежит пользователю в команде:\n'
                    '/stars $order<id> ваш_телеграм_юзернейм'
                ),
                flags=[TelegramUIEmojiFlag('🤡'), ParameterFlags.HIDE_VALUE],
            ),
        )

        self.blocked_by_user_message = self.attach_node(
            StringParameter(
                id='blocked_by_user_message',
                name='Заблокирован пользователем',
                description='Сообщение, которое будет отправлено в чат покупателю, если пользователь заблокировал ваш Telegram аккаунт.',
                default_value=(
                    '❌ $order<counterparty.username>, похоже, вы заблокировали мой Telegram аккаунт, поэтому я не могу перевести вам звезды.\n\n'
                    'Разблокируйте мой аккаунт и введите команду:\n'
                    '/stars $order<id>'
                ),
                flags=[TelegramUIEmojiFlag('🤡'), ParameterFlags.HIDE_VALUE],
            ),
        )

        self.failed_to_fetch_username_message = self.attach_node(
            StringParameter(
                id='failed_to_fetch_username',
                name='Ошибка проверки юзернейма',
                description='Сообщение, которое будет отправно в чат покупателю, если не удалось проверить юзернейм.',
                default_value=(
                    '❌ $order<counterparty.username>, не удалось проверить юзернейм @$autostars_username (ошибка на стороне Telegram).\n'
                    'Продавец уже уведомлен и спешит на помощь!\n\n'
                    'Попробуйте позже введя команду:\n'
                    '/stars $order<id>'
                ),
                flags=[TelegramUIEmojiFlag('👤'), ParameterFlags.HIDE_VALUE],
            ),
        )

        self.payload_message = self.attach_node(
            StringParameter(
                id='payload_message',
                name='Комментарий к транзакции',
                description='Сообщение, которое будет вставлено в комментарий к транзакции.',
                default_value='',
                flags=[TelegramUIEmojiFlag('📝'), ParameterFlags.HIDE_VALUE],
            ),
        )


class Other(Properties):
    def __init__(self):
        super().__init__(
            id='other',
            name='Прочее',
            description='Прочие настройки плагина.',
            flags=[TelegramUIEmojiFlag('🔩')],
        )

        self.show_sender = self.attach_node(
            ToggleParameter(
                id='show_sender',
                name='Отображать отправителя',
                description='Отображать ли отправителя в платеже.',
                default_value=True,
            )
        )

        self.refund_on_error = self.attach_node(
            ToggleParameter(
                id='refund_on_error',
                name='Возврат средств при ошибке',
                description='Возвращать ли средства за заказ при ошибке перевода TON.',
                default_value=False,
            ),
        )
