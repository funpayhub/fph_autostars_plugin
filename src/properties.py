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
            flags=[TelegramUIEmojiFlag('💬')],
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

        self.transaction_started_message = self.attach_node(
            StringParameter(
                id='transaction_started_message',
                name='Сообщение о старте транзакции',
                description='Сообщение, которое будет отправлено в чат покупателю, когда транзакция будет инициализирована.',
                default_value='',
                flags=[TelegramUIEmojiFlag('♻️')],
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
                flags=[TelegramUIEmojiFlag('✅')],
            ),
        )

        self.transaction_failed_message = self.attach_node(
            StringParameter(
                id='transaction_failed_message',
                name='Сообщение о неудачной транзакции',
                description='Сообщение, которое будет отправлено в чат покупателю, когда транзакция не будет завершена.',
                default_value=(
                    '❌ $order<counterparty.username>, не удалось перевести звезды.\n'
                    'Продавец уведомлен и придет на помощь как только сможет!'
                ),
                flags=[TelegramUIEmojiFlag('❌')],
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
                flags=[TelegramUIEmojiFlag('👤')],
            ),
        )

        self.payload_message = self.attach_node(
            StringParameter(
                id='payload_message',
                name='Комментарий к транзакции',
                description='Сообщение, которое будет вставлено в комментарий к транзакции.',
                default_value='',
                flags=[TelegramUIEmojiFlag('📝')],
            ),
        )
