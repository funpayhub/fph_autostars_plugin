from __future__ import annotations

from typing import TYPE_CHECKING

from temp.autostars.src.ton import Wallet
from temp.autostars.src.fragment_api import FragmentAPI

from funpayhub.app.dispatching import Router


if TYPE_CHECKING:
    from temp.autostars.src.ton import WalletProvider
    from temp.autostars.src.plugin import AutostarsPlugin
    from temp.autostars.src.properties import AutostarsProperties
    from temp.autostars.src.fragment_api import FragmentAPIProvider

    from funpayhub.lib.plugin import LoadedPlugin
    from funpayhub.lib.properties import StringParameter


router = Router(name='autostars')


@router.on_parameter_value_changed(
    lambda parameter, plugin: parameter.path == plugin.properties.wallet.mnemonics.path,
)
async def update_wallet(autostars_wallet: WalletProvider, parameter: StringParameter):
    if not parameter.value:
        autostars_wallet.wallet = None
        return

    autostars_wallet.wallet = await Wallet.from_mnemonics(parameter.value)


@router.on_parameter_value_changed(
    lambda parameter, plugin: parameter.path
    in [
        plugin.properties.wallet.cookies.path,
        plugin.properties.wallet.fragment_hash.path,
    ],
)
async def update_fragment_api(
    autostars_fragment_api: FragmentAPIProvider,
    plugin: LoadedPlugin[AutostarsPlugin, AutostarsProperties],
):
    if (
        not plugin.properties.wallet.cookies.value
        or not plugin.properties.wallet.fragment_hash.value
    ):
        autostars_fragment_api.api = None
        return

    autostars_fragment_api.api = FragmentAPI(
        cookies=plugin.properties.wallet.cookies.value,
        hash=plugin.properties.wallet.fragment_hash.value,
    )


@router.on_funpayhub_stopped()
async def stop_service(plugin: LoadedPlugin[AutostarsPlugin, AutostarsProperties]):
    await plugin.plugin.transfer_service.stop()
    await plugin.plugin.storage.stop()
