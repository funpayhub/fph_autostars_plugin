from __future__ import annotations


__all__ = [
    'AddFormattersMenuModification',
    'MODIFICATIONS',
]

from autostars.src.properties import AutostarsProperties

from funpayhub.lib.translater import Translater
from funpayhub.lib.telegram.ui import Menu, MenuModification
from funpayhub.lib.base_app.telegram.app.ui.callbacks import OpenMenu
from funpayhub.lib.base_app.telegram.app.properties.ui import NodeMenuContext

from funpayhub.app.properties import FunPayHubProperties
from funpayhub.app.telegram.ui.ids import MenuIds


class AddFormattersMenuModification(MenuModification, modification_id='autostars:add_formatters'):
    async def filter(
        self,
        ctx: NodeMenuContext,
        menu: Menu,
        properties: FunPayHubProperties,
    ) -> bool:
        plugin_props: AutostarsProperties = properties.plugin_properties.get_properties(
            ['com_github_qvvonk_funpayhub_autostars_plugin'],
        )
        return len(ctx.entry_path) == len(plugin_props.messages.path) + 1

    async def modify(self, ctx: NodeMenuContext, menu: Menu, translater: Translater) -> Menu:
        menu.footer_keyboard.add_callback_button(
            button_id='open_formatters_list',
            text=translater.translate('🔖 Форматтеры'),
            callback_data=OpenMenu(
                menu_id=MenuIds.formatters_list,
                new_message=True,
                data={'query': 'autostars|fph:general'},
            ).pack(),
        )
        return menu


MODIFICATIONS = {
    MenuIds.props_param_manual_input: [AddFormattersMenuModification],
}
