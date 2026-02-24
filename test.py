from funpaybotengine.dispatching import NewMessageEvent, NewSaleEvent, NewEventsPack
from funpaybotengine.runner import EventsStack

from funpaybotengine.types import Message, OrderPreview
from funpayparsers.parsers import MessagesParser, MessagesParsingOptions, \
    OrderPreviewsParsingOptions, OrderPreviewsParser
import random
import string



ADJECTIVES = [
    "fast", "dark", "silent", "frozen", "wild", "lucky",
    "ghost", "red", "blue", "iron", "cyber", "shadow"
]

NOUNS = [
    "wolf", "raven", "fox", "tiger", "dragon", "hawk",
    "ninja", "hunter", "storm", "byte", "phantom", "viper"
]


def generate_username(
    use_number: bool = True,
    number_length: int = 3,
    custom_prefix: str | None = None,
    custom_suffix: str | None = None,
) -> str:
    adjective = random.choice(ADJECTIVES)
    noun = random.choice(NOUNS)

    username = f"{adjective.capitalize()}{noun.capitalize()}"

    if custom_prefix:
        username = f"{custom_prefix}{username}"

    if custom_suffix:
        username = f"{username}{custom_suffix}"

    if use_number:
        number = ''.join(random.choices(string.digits, k=number_length))
        username += number
    return username


MESSAGE_HTML = """
<div class="chat-msg-item chat-msg-with-head" id="message-{message_id}">
    <div class="chat-message">
        <div class="media-user-name">FunPay<span class="chat-msg-author-label label label-primary">оповещение</span>
            <div class="chat-msg-date" title="20 февраля, 0:15:13">00:15:13</div>
        </div>
        
        <div class="chat-msg-body">
            <div class="alert alert-with-icon alert-info" role="alert">
                <i class="fas fa-info-circle alert-icon"></i>
                <div class="chat-msg-text">Покупатель <a href="https://funpay.com/users/0/">{username}</a> оплатил <a href="https://funpay.com/orders/{order_id}/">заказ #{order_id}</a>. Telegram, Звёзды, {stars_amount} звёзд, По username{pcs}{telegram_username}.
<a href="https://funpay.com/users/0/">{username}</a>, не забудьте потом нажать кнопку «Подтвердить выполнение заказа».</div>
            </div>
        </div>
    </div>
</div>
"""

ORDER_HTML = """
<a href="https://funpay.com/orders/{order_id}/" class="tc-item info">
    <div class="tc-date">
            <div class="tc-date-time">20 февраля, 0:16</div>
            <div class="tc-date-left">2 дня назад</div>
    </div>
    <div class="tc-order">#{order_id}</div>
    <div class="order-desc">
        <div>{stars_amount} звёзд, По username{pcs}{telegram_username}</div>
        <div class="text-muted">Telegram, Звёзды</div>
    </div>
    <div class="tc-user">
        <div class="media media-user offline">
            <div class="media-left">
                <div class="avatar-photo pseudo-a" tabindex="0" data-href="https://funpay.com/users/0/" style="background-image: url(/img/layout/avatar.png);"></div>
            </div>
            <div class="media-body">
                <div class="media-user-name">
                    <span class="pseudo-a" tabindex="0" data-href="https://funpay.com/users/0/">{username}</span>
                </div>
                <div class="media-user-status">был 2 дня назад</div>
            </div>
        </div>
    </div>                                        
    <div class="tc-status text-primary">Оплачен</div>
    <div class="tc-price text-nowrap tc-seller-sum">1.00 <span class="unit">₽</span></div>                                                        
</a>
"""


def fake_event(
    telegram_username: str | None = None,
    amount: int | None = None,
    pcs: int | None = None
) -> NewSaleEvent:
    username = generate_username()
    order_id = 'AST' + ''.join(random.choices(string.ascii_uppercase, k=5))
    stars_amount = amount or random.randint(50, 10000)
    pcs = pcs or random.randint(1, 5)
    if pcs:
        pcs = f', {pcs} шт.'
    else:
        pcs = ''

    telegram_username = telegram_username or ''.join(random.choices(string.ascii_lowercase, k=25))
    telegram_username = f', {telegram_username}'

    message_html_formatted = MESSAGE_HTML.format(
        message_id=random.randint(1000000000, 9999999999),
        username=username,
        order_id=order_id,
        telegram_username=telegram_username,
        pcs=pcs,
        stars_amount=stars_amount
    )

    order_html_formatted = ORDER_HTML.format(
        order_id=order_id,
        username=username,
        telegram_username=telegram_username,
        pcs=pcs,
        stars_amount=stars_amount
    )

    msg_options = MessagesParsingOptions(empty_raw_source=True)
    messages = MessagesParser(raw_source=message_html_formatted, options=msg_options).parse()
    message = Message.model_validate(messages[0], context={'chat_id': -1})

    order_options = OrderPreviewsParsingOptions(empty_raw_source=True)
    orders = OrderPreviewsParser(raw_source=order_html_formatted, options=order_options).parse()
    order = OrderPreview.model_validate(orders.orders[0])

    new_msg_event = NewMessageEvent(object=message, tag='autostars')
    new_sale_event = NewSaleEvent(
        object=message,
        tag='autostars',
        related_new_message_event=new_msg_event
    )
    new_sale_event._order_preview = order
    return new_sale_event


def fake_events_stack(valid_username: bool = False, amount: int = 1) -> EventsStack:
    events = []
    for i in range(amount):
        events.append(
            fake_event(
                valid_username=valid_username if not valid_username else bool(random.randint(0, 1))
            )
        )

    events_stack = EventsStack(events=())
    events.insert(0, NewEventsPack(object=events_stack.id))
    events_stack.events = tuple(events)
    return events_stack


def fake_events_stack_from_events(*events: NewSaleEvent) -> EventsStack:
    events = list(events)
    events_stack = EventsStack(events=())
    events.insert(0, NewEventsPack(object=events_stack.id))
    events_stack.events = tuple(events)
    return events_stack