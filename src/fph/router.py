from __future__ import annotations

from typing import TYPE_CHECKING

from funpayhub.app.dispatching import Router


if TYPE_CHECKING:
    from autostars.src.plugin import AutostarsPlugin
    from autostars.src.properties import AutostarsProperties
    from autostars.src.autostars_provider import AutostarsProvider

    from funpayhub.lib.plugin import LoadedPlugin
    from funpayhub.lib.properties import StringParameter


router = Router(name='autostars')


@router.on_parameter_value_changed(
    lambda parameter, plugin: parameter.path == plugin.properties.wallet.mnemonics.path,
)
async def update_wallet(autostars_provider: AutostarsProvider, parameter: StringParameter):
    await autostars_provider.change_wallet(parameter.value)


@router.on_parameter_value_changed(
    lambda parameter, plugin: parameter.path
    in [
        plugin.properties.wallet.cookies.path,
        plugin.properties.wallet.fragment_hash.path,
    ],
)
async def update_fragment_api(
    autostars_provider: AutostarsProvider,
    plugin: LoadedPlugin[AutostarsPlugin, AutostarsProperties],
):
    await autostars_provider.change_fragment(
        plugin.properties.wallet.cookies.value, plugin.properties.wallet.fragment_hash.value
    )


@router.on_funpayhub_stopped()
async def stop_service(plugin: LoadedPlugin[AutostarsPlugin, AutostarsProperties]):
    await plugin.plugin.transfer_service.stop()
    await plugin.plugin.provider.storage.stop()
